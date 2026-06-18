# AI Carousel Generation (build spec) — distilled from carousel-generator

## Summary
Turn a one-line topic into a validated, editor-ready carousel document using OpenAI function
calling driven by a Zod schema. The key move is a **styled/unstyled schema split**: the LLM is
forced to call a single function whose parameters are the JSON Schema of a *content-only*
("unstyled") document; its output is validated, then re-parsed through the *styled* schema which
injects all presentation defaults deterministically. The model never picks styling.

## Core logic (inlined)

`generateCarouselSlides(topicPrompt, apiKey)` — verbatim from `src/lib/langchain.ts`:

```ts
import { ChatOpenAI } from "langchain/chat_models/openai";
import { HumanMessage, SystemMessage } from "langchain/schema";
import { z } from "zod";
import { zodToJsonSchema } from "zod-to-json-schema";
import { MultiSlideSchema, UnstyledMultiSlideSchema } from "@/lib/validation/slide-schema";
import { UnstyledDocumentSchema } from "@/lib/validation/document-schema";
import {
  UnstyledTitleSchema, UnstyledDescriptionSchema, UnstyledSubtitleSchema,
} from "@/lib/validation/text-schema";

const carouselFunctionSchema = {
  name: "carouselCreator",
  description: "Creates a carousel with multiple slides for a given topic.",
  parameters: zodToJsonSchema(UnstyledDocumentSchema, {
    definitions: { UnstyledTitleSchema, UnstyledSubtitleSchema, UnstyledDescriptionSchema },
  }),
};

export async function generateCarouselSlides(
  topicPrompt: string, apiKey: string
): Promise<z.infer<typeof MultiSlideSchema> | null> {
  const model = startModelClient(apiKey);
  const result = await model.invoke([
    new SystemMessage(`
      Create a Carousel of slides following these rules

      Arguments Schema Instructions:
       - Respect the argument schema and only use the allowed values for element type, which are 'Title', 'Subtitle' and 'Description'.
       - Each slide can use the multiple elements and they can be of different type or not.
       - Respect the 'maxLength' value which is the maximum number of characters in a given field. Write less than 70% of that number.

      Guidelines:
       - Create 8-15 slides.
       - Each slide has 2-3 different elements. E.g. [Title, Description], or [Title, Subtitle], or [Subtitle, Description].
       - Each slide All the elements in that slide are about that idea.
       - Adapt, reorganize and rephrase the content to fit the slides format.
       - Add Emojis to the text in Title, Subtitle and Description.
       - Don't add slide numbers.
       - Description element text should be short.
       `),
    new HumanMessage(topicPrompt),
  ]);

  const jsonParsed = JSON.parse(result.additional_kwargs.function_call?.arguments || "");
  const unstyledDocumentParseResult = UnstyledDocumentSchema.safeParse(jsonParsed);
  if (unstyledDocumentParseResult.success) {
    return MultiSlideSchema.parse(unstyledDocumentParseResult.data.slides);
  } else {
    console.log("Error in carousel generation schema");
    console.error(unstyledDocumentParseResult.error);
    console.log(jsonParsed);
    return null;
  }
}

function startModelClient(api_key: string) {
  return new ChatOpenAI({
    openAIApiKey: api_key, modelName: "gpt-4o-mini", temperature: 0,
  }).bind({
    functions: [carouselFunctionSchema],
    function_call: { name: "carouselCreator" },
  });
}
```

### The styled/unstyled split (the load-bearing pattern)
Two Zod schemas per element. The **unstyled** one is what the LLM fills; the **styled** one merges
in defaults so the rest of the app gets a complete object for free. From `src/lib/validation/text-schema.tsx`:

```ts
export const UnstyledTitleSchema = z.object({
  type: z.literal(ElementType.enum.Title).describe(`Indicates that this is a 'Title'.`),
  text: z.string().max(160, { message: "Title must not be longer than 160 characters." })
         .describe("A short title").default(""),
});
export const TitleSchema = UnstyledTitleSchema.merge(z.object({
  type: z.literal(ElementType.enum.Title).default(ElementType.enum.Title),
  style: TextStyleSchema.default({}),   // <-- styling injected here, not by the LLM
}));
// Subtitle identical (max 160). Description: text max ~240 (described, not hard-enforced).

export const TextStyleSchema = z.object({
  fontSize: z.enum(["Small","Medium","Large"]).default("Medium"),
  align:    z.enum(["Left","Center","Right"]).default("Left"),
});
```

`UnstyledDocumentSchema = z.object({ slides: UnstyledMultiSlideSchema })`. Each slide is a
discriminated union (`z.discriminatedUnion("type", ...)`) of element schemas plus a `SlideType`
enum (`Intro | Content | Outro | Common`) and optional background image. `MultiSlideSchema` is the
styled array; calling `.parse()` on the LLM's content array fills every `.default()`.

## Data contracts
- **Input:** `topicPrompt: string`, `apiKey: string`.
- **LLM call:** OpenAI `gpt-4o-mini`, `temperature: 0`, bound with one function `carouselCreator`
  and `function_call: { name: "carouselCreator" }` (forces the call — no free text returned).
- **Function parameters:** JSON Schema produced by `zodToJsonSchema(UnstyledDocumentSchema, {definitions})`.
- **Raw model output:** `result.additional_kwargs.function_call.arguments` is a JSON *string*.
- **Output:** `z.infer<typeof MultiSlideSchema>` (array of styled slides) or `null` on validation failure.
- **Element shape (unstyled):** `{ type: "Title"|"Subtitle"|"Description", text: string }`.
- **Element shape (styled):** unstyled + `{ style: { fontSize, align } }`.

## Dependencies & assumptions
- `langchain` (v0.0.x API: `langchain/chat_models/openai`, `langchain/schema`), `openai`, `zod`,
  `zod-to-json-schema`. NOTE: this is the legacy LangChain import path; on current `@langchain/openai`
  use `new ChatOpenAI({ model, temperature }).bind({ functions, function_call })` or, better, the
  modern equivalent `.withStructuredOutput(zodSchema)` which removes the manual `zodToJsonSchema`
  + JSON.parse + safeParse dance entirely.
- Requires an OpenAI key (passed in, not read from env here — env handling is in the server action).
- Swappable: any function-calling-capable model; `gpt-4o-mini` chosen for cost.

## To port this, you need:
- [ ] A Zod content model for your output, split into unstyled (LLM-filled) + styled (defaults).
- [ ] `.describe()` text on each field — it becomes the model's field-level instruction.
- [ ] A forced single-function call (or `withStructuredOutput`) so output is guaranteed structured.
- [ ] A `safeParse` gate that returns `null`/empty on mismatch instead of throwing into your UI.
- [ ] A second `.parse()` through the styled schema to inject presentation defaults.

## Gotchas
- `function_call.arguments` is a **string** — `JSON.parse` it; an empty/absent call → `|| ""` →
  `JSON.parse("")` throws. Guard it (the original doesn't fully).
- The model can still emit text over `maxLength`; Zod's `.max()` will then **fail the whole parse**.
  The "write <70%" prompt is the soft mitigation; consider `.catch()`/truncation for robustness.
- Temperature 0 makes output near-deterministic — good for structure, poor for variety; expose
  temperature if users want alternates.
- Legacy LangChain version pin matters; the import paths above don't exist in current LangChain.
- Description `maxLength` is only *described*, not enforced with `.max()` — asymmetry to watch.

## Origin (reference only)
`src/lib/langchain.ts` (full logic), `src/lib/validation/text-schema.tsx`,
`src/lib/validation/document-schema.tsx`, `src/lib/validation/slide-schema.tsx`,
`src/lib/validation/element-type.tsx`. Invoked by the server action in `src/app/actions.tsx`.
