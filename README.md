# Image store for the Used Bike Guide

Photos uploaded from the guide's web interface land here, one per entry, named after
the entry id — `bimota-db1-1985.jpg`.

This branch exists on its own so that uploading a photo does **not** trigger a GitHub
Pages rebuild. Pages builds from `main`; commits here are ignored by it, which matters
because Pages throttles at roughly ten builds an hour and a busy afternoon of uploads
would otherwise exhaust that.

Images are served to the page directly from
`raw.githubusercontent.com/wolfpunk25/Used-Bike-Guide/images/…`, which updates the
moment a commit lands rather than waiting on a deploy.

Images are resized to 1600px on the long edge before upload. They are for
identification and cross-reference only — print-resolution originals belong in the
picture library, not here.
