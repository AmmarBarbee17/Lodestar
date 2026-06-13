-- Shortcode: {{< model path/to/MDL-foo.glb >}}
--
-- Stub. The author will fill in HTML (<model-viewer>) and PDF
-- (static figure from an auto-generated PNG) branches later. For now,
-- this returns a visible TODO placeholder so missing implementations
-- are obvious in every render target.

function model(args, kwargs, meta)
  local src = pandoc.utils.stringify(args[1] or "TODO")
  return pandoc.RawInline("markdown",
    "`[TODO model shortcode — src=" .. src .. "]`")
end

return {
  ["model"] = model,
}
