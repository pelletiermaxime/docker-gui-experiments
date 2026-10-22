import { Cmd, asciiBytes, utf8Bytes } from "@native-sdk/core";
import { applyTextInputEvent, containsIgnoreCase, type TextEditState, type TextInputEvent } from "@native-sdk/core/text";
import { type VirtualListRange } from "@native-sdk/core/events";

export interface Container {
  readonly id: Uint8Array;
  readonly name: Uint8Array;
  readonly image: Uint8Array;
  readonly state: Uint8Array;
  readonly status: Uint8Array;
}
export interface Model {
  readonly containers: readonly Container[];
  readonly search: TextEditState;
  readonly busy: boolean;
  readonly notice: Uint8Array;
}
export type Msg =
  | { readonly kind: "refresh" }
  | { readonly kind: "search_edit"; readonly event: TextInputEvent }
  | { readonly kind: "loaded"; readonly code: number; readonly output: Uint8Array }
  | { readonly kind: "failed"; readonly reason: Uint8Array };
export const viewUnbound = ["containers", "loaded", "failed"] as const;

export function initialModel(): [Model, Cmd<Msg>] {
  return [
    { containers: [], search: { text: asciiBytes(""), selection: { anchor: 0, focus: 0 }, composition: null }, busy: true, notice: asciiBytes("Loading Docker...") },
    Cmd.spawn([asciiBytes("node"), asciiBytes("docker.mjs")], { key: "docker", collect: true, exit: "loaded", err: "failed" }),
  ];
}
export function query(model: Model): Uint8Array { return model.search.text; }
export function filtered(model: Model): readonly Container[] {
  return model.containers.filter(c => containsIgnoreCase(c.name, model.search.text) || containsIgnoreCase(c.image, model.search.text) || containsIgnoreCase(c.state, model.search.text) || containsIgnoreCase(c.status, model.search.text));
}
export function count(model: Model): number { return filtered(model).length; }
export function rowExtent(_: Model, index: number): number { return 36; }
export function rows(model: Model, range: VirtualListRange): readonly Container[] {
  return filtered(model).slice(range.start_index, range.end_index);
}
function splitBytes(bytes: Uint8Array, delimiter: number): readonly Uint8Array[] {
  const parts: Uint8Array[] = [];
  let start = 0;
  for (let i = 0; i < bytes.length; i++) {
    if (bytes[i] === delimiter) { parts.push(bytes.slice(start, i)); start = i + 1; }
  }
  if (start < bytes.length) parts.push(bytes.slice(start));
  return parts;
}
export function update(model: Model, msg: Msg): Model | [Model, Cmd<Msg>] {
  switch (msg.kind) {
    case "refresh":
      if (model.busy) return model;
      return [{ ...model, busy: true, notice: asciiBytes("Loading Docker...") }, Cmd.spawn([asciiBytes("node"), asciiBytes("docker.mjs")], { key: "docker", collect: true, exit: "loaded", err: "failed" })];
    case "search_edit": {
      const edited = applyTextInputEvent(model.search, msg.event, 256);
      return edited === null ? model : { ...model, search: edited };
    }
    case "failed":
      return { ...model, busy: false, notice: utf8Bytes(`Docker error: ${msg.reason}`) };
    case "loaded": {
      if (msg.code !== 0) return { ...model, busy: false, notice: utf8Bytes(`Docker error: ${msg.output}`) };
      const lines = splitBytes(msg.output, 10);
      const containers: Container[] = [];
      for (let i = 1; i < lines.length; i++) {
        const fields = splitBytes(lines[i], 9);
        if (fields.length !== 5) return { ...model, busy: false, notice: asciiBytes("Invalid Docker worker response") };
        containers.push({ id: fields[0], name: fields[1], image: fields[2], state: fields[3], status: fields[4] });
      }
      return { ...model, containers: containers, busy: false, notice: lines[0] };
    }
  }
}
