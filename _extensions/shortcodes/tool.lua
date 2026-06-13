-- Shortcode: {{< tool tool-id >}}
--
-- Stub. Final version will look up the id in `tools.yml`, render a
-- callout with name/image/spec in HTML, and a labeled figure in PDF.
-- For now, returns a visible TODO placeholder so gaps are obvious.

function tool(args, kwargs, meta)
  local id = pandoc.utils.stringify(args[1] or "TODO")
  return pandoc.RawInline("markdown",
    "`[TODO tool shortcode — id=" .. id .. "]`")
end

return {
  ["tool"] = tool,
}
