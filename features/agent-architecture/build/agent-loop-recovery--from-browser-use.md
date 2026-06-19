# Agent Loop & Recovery (build spec) — distilled from browser-use

## Summary

A robust think->act->observe loop for a tool-using LLM agent: each step build a 3-slot message, call the LLM with a forced structured output, execute the returned action list, record history, and loop until done or `max_steps`. Layered recovery: nuanced failure counting, two-stage forced-done, soft loop detection, replan/explore nudges, provider fallback, and connection-drop tolerance.

## Core logic (inlined)

### Main loop — `Agent.run(max_steps=500)`
```
register signal handler (Ctrl-C -> pause/resume/force-exit)
emit session/task events; await browser_session.start()
await _execute_initial_actions()           # wrapped in wait_for(step_timeout)
while state.n_steps <= max_steps:
    if state.paused: await external_pause_event
    if state.consecutive_failures >= settings.max_failures + int(final_response_after_failure): break
    if state.stopped: break
    step_info = AgentStepInfo(step_number=current, max_steps=max_steps)
    is_done = await _execute_step(step_info)   # wraps step() in wait_for(step_timeout=180s); on TimeoutError: consecutive_failures+=1, store ActionResult(error), bump n_steps
    if is_done: break
else:  # loop exhausted without done
    history.add(error item)
return self.history    # AgentHistoryList
```
With defaults (`max_failures=5`, `final_response_after_failure=True`) the loop hard-breaks at **6** consecutive failures; failure 5 still gets a forced-done LLM call (below).

### One step — `Agent.step(step_info)`
```
await wait_if_captcha_solving()            # pause timing; inject captcha outcome as ActionResult
try:
    bss = await _prepare_context(step_info)         # phase 1
    await _get_next_action(bss)                     # phase 2a
    await _execute_actions()                        # phase 2b
    await _post_process()                           # phase 3
except Exception as e: await _handle_step_error(e)
finally: await _finalize(bss)                       # writes history; n_steps += 1 HERE
```

### Phase 1 — `_prepare_context`
```
bss = await browser_session.get_browser_state_summary(include_screenshot=True)
_check_and_update_downloads(); _check_stop_or_pause()    # raises InterruptedError if stopped/paused
_update_action_models_for_page(url)                      # rebuild action schema for current domain
page_actions = tools.registry.get_prompt_description(url)
message_manager.prepare_step_state(bss, last_model_output, last_result, step_info)  # clears context_messages
_maybe_compact_messages(step_info)                      # optional LLM summarization of old history
message_manager.create_state_messages(...)              # build the state slot
# conditional context-message injectors (all ephemeral):
if steps_used >= 75%: inject_budget_warning()
if consecutive_failures >= planning_replan_on_stall(3) and plan: inject_replan_nudge()
if n_steps >= planning_exploration_limit(5) and no plan: inject_exploration_nudge()
inject_loop_detection_nudge()                           # escalating, see detector below
if is_last_step: force schema = DoneAgentOutput + context msg     # _force_done_after_last_step
if consecutive_failures >= max_failures(5): force schema = DoneAgentOutput + "you failed N times; only tool is done"  # _force_done_after_failure
```

### Message structure (3 slots) — sent every step
```
get_messages() -> [system_message, state_message, *context_messages]
# system_message: set once at init from a markdown template; never replaced
# state_message: rebuilt each step:
#   <user_request> task
#   <agent_history> formatted HistoryItem list (evaluation+memory+next_goal+action_results; errors when present;
#                   optionally compacted to a summary after compact_every_n_steps)
#   plan / filesystem / todo / sensitive-data placeholders
#   browser state: url, title, tabs, scroll, page stats, DOM/selector text, screenshot (if use_vision)
#   step counter + date LAST  <-- maximizes prompt-cache prefix hits
# context_messages: nudges/warnings/forced-done; CLEARED at start of every step
```

### Phase 2a — `_get_next_action`
```
msgs = message_manager.get_messages()
model_output = await wait_for(_get_model_output_with_retry(msgs), timeout=llm_timeout=60s)
# get_model_output: resp = await llm.ainvoke(msgs, output_format=self.AgentOutput, session_id=...)
#                   parsed = resp.completion; truncate action[] to max_actions_per_step; restore shortened URLs
# _get_model_output_with_retry: one retry if action[] empty; if still empty -> synthesize done(success=False)
state.last_model_output = model_output; _check_stop_or_pause(); _handle_post_llm_processing()
```

### AgentOutput schema (the forced structured output)
```
class AgentOutput(BaseModel):
    thinking: str|None = None                  # dropped in no-thinking/flash variants
    evaluation_previous_goal: str|None         # required in normal schema
    memory: str|None                           # required
    next_goal: str|None                        # required
    current_plan_item: int|None
    plan_update: list[str]|None
    action: list[ActionModel]                  # required, min_items=1
# normal required: [evaluation_previous_goal, memory, next_goal, action]
# flash_mode required: [memory, action]   (drops evaluation/next_goal/thinking + planning)
# DoneAgentOutput: action restricted to only the `done` action (used to force termination)
```

### Phase 2b — `_execute_actions` -> `multi_act(actions)`
```
for i, action in enumerate(actions):
    if i>0 and action is 'done': break          # done only valid as a single action
    if i>0: sleep(wait_between_actions)
    _check_stop_or_pause(); capture pre_url, pre_focus
    result = await tools.act(action, browser_session, ...)   # -> ActionResult
    results.append(result)
    if result.is_done or result.error or last: break
    if action.terminates_sequence: break        # navigate/search/go_back/switch
    if url_changed or focus_changed: break
    # InterruptedError / connection error -> re-raise; other Exception -> append ActionResult(error); return
return results
```

### Phase 3 — `_post_process`
```
_check_and_update_downloads(); _update_plan_from_model_output(); _update_loop_detector_actions()  # exclude wait/done/go_back
if len(last_result)==1 and last_result[0].error: consecutive_failures += 1; return    # single-action error only
elif consecutive_failures > 0: consecutive_failures = 0                                # reset on any non-error/multi step
if last_result[-1].is_done: log final
```

### `_handle_step_error` routing
| Exception | Effect on consecutive_failures |
|---|---|
| InterruptedError | none (warn only) |
| connection error, browser reconnecting | none — wait for reconnect, store error result |
| connection error, browser truly closed | none — set state.stopped=True |
| anything else (ValidationError, LLM TimeoutError, ...) | +1, store ActionResult(error=formatted) |

### Loop detector (`ActionLoopDetector`)
```
rolling window (default 20) of action hashes; hash normalized per type:
  search -> sorted tokens; click -> index; navigate -> full URL; scroll -> direction+index
page fingerprint = sha256(dom_text + url + element_count); track consecutive stagnant pages
get_nudge_message(): escalating context msg at repetition counts 5/8/12, and page-stagnation >=5
# soft constraint — agent may still repeat
```

### Provider fallback & history
```
on ModelRateLimitError / ModelProviderError(401|402|429|5xx): self.llm = self._fallback_llm (permanent for run)
_finalize: build StepMetadata; _make_history_item(model_output, bss, last_result, meta):
  interacted elements -> DOMInteractedElement[]; store screenshot -> path;
  BrowserStateHistory(url,title,tabs,interacted_element,screenshot_path); history.add_item(AgentHistory(...))
```

## Data contracts
```
ActionResult: { is_done: bool, success: bool|None, error: str|None, extracted_content: str|None,
                long_term_memory: str|None, images: list|None, attachments: list|None }
AgentState (serializable for resume): { n_steps, consecutive_failures, last_model_output, last_result,
                plan: list[PlanItem{text,status: pending|current|done|skipped}], loop_detector }
AgentSettings (knobs): { max_failures=5, final_response_after_failure=True, max_actions_per_step,
                step_timeout=180, llm_timeout=60, flash_mode, use_vision, planning_replan_on_stall=3,
                planning_exploration_limit=5, compact_every_n_steps, wait_between_actions }
AgentHistory(step): { model_output, result: list[ActionResult], state: BrowserStateHistory, metadata: StepMetadata }
```

## Dependencies & assumptions
- An LLM client with forced structured output: `await llm.ainvoke(messages, output_format=PydanticModel) -> completion` (see [[multi-provider-llm-abstraction--from-browser-use]]).
- A perception source: `browser_session.get_browser_state_summary()` (see [[indexed-dom-serialization--from-browser-use]]).
- An action executor: `tools.act(action, ...) -> ActionResult` (see [[action-tool-registry--from-browser-use]]).
- A fallback LLM instance (optional). An event bus for session/step events (optional — swappable for logging).

## To port this, you need:
- [ ] A `while n_steps <= max_steps` loop with the counter bumped in finalize (so timeouts can't spin).
- [ ] A 3-slot message manager (system fixed / state rebuilt / context cleared each step), volatile fields last for cache hits.
- [ ] A mutable output schema you can swap to a done-only variant to force termination.
- [ ] The failure-counting rules (single-action errors only; resets; interrupts/connection excluded) and the two-stage forced-done at `max_failures` and `max_failures+1`.
- [ ] An action-hash + page-fingerprint loop detector emitting soft nudges.
- [ ] Per-step + per-LLM timeouts, an empty-action retry, and provider fallback on rate-limit/5xx.
- [ ] A serializable history record per step (model output + results + page state + screenshot).

## Gotchas
- **Counter incremented in finalize, not the loop head** — a step that times out before finalize must bump it manually or you get an infinite loop.
- **Multi-action error steps don't increment failures** — intentional ("partial progress"), but can hide a stuck agent.
- **Forced-done is a schema swap**, relying on the provider enforcing structured output; if your provider doesn't, "stop" becomes a suggestion.
- **`done` mid-list is dropped** — finishing must be a single action.
- **Context nudges are wiped each step** — don't expect them to persist; re-inject every step they apply.
- **`max_failures` vs `max_failures+1`**: step 5 gets a graceful done call; step 6 breaks without calling the model. Off-by-one here changes behavior.
- **URL shortening**: long URLs are shortened before the LLM call and restored in the parsed output — keep the restore step or the model's URLs won't resolve.

## Origin (reference only)
Repo: https://github.com/browser-use/browser-use (`main`). `browser_use/agent/service.py`
(`Agent.run`/`step`/`_prepare_context`/`_get_next_action`/`multi_act`/`_post_process`/`_handle_step_error`/`_finalize`),
`browser_use/agent/views.py` (`AgentOutput`,`AgentBrain`,`AgentState`,`AgentHistory`,`ActionResult`,`AgentSettings`,`ActionLoopDetector`),
`browser_use/agent/message_manager/` (service.py + views.py), `browser_use/agent/prompts.py`.
Gaps to verify if reachable: exact `AgentMessagePrompt.get_user_message()` template; system-prompt markdown
files; `_update_agent_history_description` truncation (200-char error / 60k content caps); compaction prompt.
