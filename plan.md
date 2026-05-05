1. **Add `focus-visible` to missing buttons**
   - Target the primary files containing multiple interactive buttons lacking keyboard focus outlines.
   - Files to update:
     - `web/app/page.tsx`
     - `web/app/components/BenchmarkResults.tsx`
     - `web/app/offline/page.tsx`
     - `web/app/agent-generator/page.tsx`
     - `web/app/skills-generator/page.tsx`
   - I will modify only a subset (to keep changes < 50 lines) to apply `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color]` consistent with the surrounding Tailwind classes.

2. **Add "Clear Search" CTA to "No results found" in `RagSearchPanel.tsx`**
   - I will modify `web/app/components/context/RagSearchPanel.tsx`'s empty state to include a "Clear Search" button. This aligns with Palette's empty state CTA philosophy.
   - Note: The journal says "Empty states without Call-to-Action (CTA) buttons create friction".

Wait, the prompt says "ONE micro-UX improvement that makes the interface more intuitive". Let's stick to **adding the CTA in RagSearchPanel.tsx** as it's exactly < 50 lines, highly visible, and explicitly mentioned in my journal learnings ("Empty State Call-to-Actions"). Adding `focus-visible` to 30+ buttons might violate the < 50 lines rule.

*Revised Plan:*
1. **Target:** `web/app/components/context/RagSearchPanel.tsx`
2. **Implementation:** Update the "No results found" empty state to include a `<button type="button" onClick={() => setQuery("")}>Clear Search</button>` styled appropriately with `focus-visible`.
3. **Verify:**
   - `pnpm format`
   - `pnpm lint`
   - `pnpm test`
   - Create a Playwright screenshot of the change (frontend verification).
4. **Pre-commit:** Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.
5. **Submit:** Submit the change with title "🎨 Palette: [UX improvement]"
