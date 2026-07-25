# PPT content markdown protocol

This compatibility protocol is retained only for parsing historical PPT content.
New courseware must be generated through OpenMAIC Classroom Studio.

Each slide starts with `## Slide N`, followed by metadata bullets and a
`### Blocks` section. Keep titles, body text, speaker notes, and source
references explicit. Do not emit HTML, scripts, local file paths, or executable
commands.

