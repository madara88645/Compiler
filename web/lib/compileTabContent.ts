import type { CompileResponse } from "./api/types";

export type CompileOutputTab = "system" | "user" | "plan" | "expanded";

/** Prefer v2 prompt fields when present — matches API/CLI export behavior. */
export function getCompileTabContent(
  result: CompileResponse,
  activeTab: CompileOutputTab,
): string {
  if (activeTab === "system") {
    return result.system_prompt_v2 || result.system_prompt || "";
  }

  if (activeTab === "user") {
    return result.user_prompt_v2 || result.user_prompt || "";
  }

  if (activeTab === "plan") {
    return result.plan_v2 || result.plan || "";
  }

  return result.expanded_prompt_v2 || result.expanded_prompt || "";
}
