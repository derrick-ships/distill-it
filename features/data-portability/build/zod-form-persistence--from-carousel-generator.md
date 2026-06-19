# Zod Form Persistence & JSON Portability (build spec) — distilled from carousel-generator

## Summary
A server-less document model: one React Hook Form document, one Zod `DocumentSchema`, used for
(a) **auto-persist to localStorage** on every change, (b) **validated rehydrate** that *clears
storage and returns defaults* when the saved data no longer matches the schema (self-healing across
schema changes), and (c) **per-field JSON import/export** validated by the matching sub-schema
before `setValue`. The reusable idea: treat localStorage as untrusted input and gate it with Zod.

## Core logic (inlined)

Persist + rehydrate — `src/lib/hooks/use-persist-form.tsx` (verbatim):

```tsx
import { useCallback, useEffect } from "react";

export function useRetrieveFormValues<T, DocumentSchema>(
  localStorageKey: string,
  defaultValues: T,
  schema: typeof DocumentSchema
) {
  const getSavedData: () => T | undefined = useCallback(() => {
    const localStorage = typeof window !== "undefined" ? window.localStorage : undefined;
    if (!localStorage) return undefined;
    let data = localStorage?.getItem(localStorageKey);
    if (data) {
      try {
        const parsedData = JSON.parse(data) as T;
        if (!schema) return parsedData;
        const safeParseResult = schema.safeParse(parsedData);
        if (safeParseResult.success) {
          return safeParseResult.data as T;
        } else {
          console.error(safeParseResult.error);
          localStorage.clear();            // schema drift / tamper -> wipe & reset
          return defaultValues;
        }
      } catch (err) {
        console.log(err);                  // corrupt JSON -> fall through to defaults
      }
    }
    return defaultValues;
  }, [defaultValues, localStorageKey, schema]);
  return { getSavedData };
}

export const usePersistFormValues = ({
  localStorageKey, values,
}: { localStorageKey: string; values: any }) => {
  useEffect(() => {
    const localStorage = typeof window !== "undefined" ? window.localStorage : undefined;
    localStorage?.setItem(localStorageKey, JSON.stringify(values));   // no debounce: writes every change
  }, [values, localStorageKey]);
  return;
};
```

Wiring (pattern): `const form = useForm({ resolver: zodResolver(DocumentSchema), defaultValues: getSavedData() ?? DEFAULTS })`,
then `usePersistFormValues({ localStorageKey, values: form.watch() })`.

JSON import — `src/lib/hooks/use-fields-file-importer.tsx` (verbatim, trimmed):

```tsx
import { useFormContext } from "react-hook-form";
import { ConfigSchema } from "@/lib/validation/document-schema";
import { MultiSlideSchema } from "@/lib/validation/slide-schema";

export function useFieldsFileImporter(field: "config" | "slides") {
  const { setValue } = useFormContext();
  const [fileReader, setFileReader] = useState<FileReader | null>(null);
  const [configured, setConfigured] = useState(false);

  useEffect(() => { setFileReader(new FileReader()); }, []);

  if (fileReader && !configured) {
    setConfigured(true);
    fileReader.onload = (e: ProgressEvent) => {
      const result = JSON.parse((e.target as FileReader).result as string);
      if (field == "config") {
        const parsed = ConfigSchema.parse(result);        // throws on bad file
        if (parsed) setValue(field, parsed);
      } else if (field == "slides") {
        const parsed = MultiSlideSchema.parse(result);
        if (parsed) setValue(field, parsed);
      }
    };
  }

  const handleFileSubmission = (files: FileList) => {
    if (files?.length && fileReader) fileReader.readAsText(files[0]);
  };
  return { handleFileSubmission };
}
```

JSON export (pattern — `json-exporter.tsx`): serialize the slice and download.

```ts
function downloadJson(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: `${filename}.json` });
  a.click();
  URL.revokeObjectURL(url);
}
// export whole doc: downloadJson(form.getValues(), form.getValues("filename"))
// or a slice:       downloadJson(form.getValues("config"), "config")
```

## Data contracts
- `DocumentSchema = z.object({ slides: MultiSlideSchema, config: ConfigSchema, filename: z.string() })`.
- `ConfigSchema = z.object({ brand, theme, fonts, pageNumber })`.
- localStorage value: `JSON.stringify(documentValues)` under one app-chosen key string.
- Import file: a `.json` whose top-level shape equals `ConfigSchema` (config import) or
  `MultiSlideSchema` (slides import).
- Rehydrate contract: returns `safeParse`d data on success; **clears storage + returns defaults** on
  schema failure; returns defaults on JSON parse error or empty storage.

## Dependencies & assumptions
- `zod`, `react-hook-form` (`useForm`, `useFormContext`, `setValue`, `watch`/`getValues`), `@hookform/resolvers/zod`.
- Browser `localStorage` + `FileReader` + `Blob`/`URL.createObjectURL`. SSR-guarded via
  `typeof window !== "undefined"`.
- Swappable: storage backend (IndexedDB), and you can add a `useFieldsFileImporter("document")`
  branch validating the full `DocumentSchema` for whole-file import.

## To port this, you need:
- [ ] A single Zod schema for your document (+ sub-schemas for per-field import).
- [ ] A form (or store) whose values you can serialize/replace wholesale.
- [ ] A read path that `safeParse`s stored data and resets on failure (don't blindly trust storage).
- [ ] SSR guards (`typeof window`) if on Next.js/SSR.
- [ ] File download + `FileReader` import helpers.

## Gotchas
- **No debounce on write** — every change re-stringifies and writes the whole document. Add a
  debounce (e.g. 300–500ms) for large docs or high-frequency editing.
- **`localStorage.clear()` nukes the entire origin**, not just this key — use `removeItem(key)` if
  the app stores anything else.
- Import uses `.parse()` (throws) not `.safeParse()` — wrap in try/catch and surface a user error,
  or it bubbles uncaught.
- Rehydrating into `defaultValues` only happens at `useForm` init; calling `getSavedData()` later
  won't retro-apply unless you `reset()` the form.
- Schema changes silently wipe saved work (by design here). If that's costly, add a `version` field
  and a migration step instead of discard-on-mismatch.
- `FileReader` is configured lazily inside render guarded by a flag — a `useEffect`/`useCallback`
  setup is cleaner and avoids the set-state-during-render smell.

## Origin (reference only)
`src/lib/hooks/use-persist-form.tsx` (persist/rehydrate), `src/lib/hooks/use-fields-file-importer.tsx`
(import), `src/components/json-importer.tsx` + `src/components/json-exporter.tsx` (UI),
`src/lib/validation/document-schema.tsx` (`DocumentSchema`/`ConfigSchema`).
