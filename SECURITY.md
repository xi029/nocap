# Security

Report suspected security issues privately through GitHub's private vulnerability reporting on this repository when enabled. If unavailable, contact the maintainer through their public GitHub profile without posting secrets or an exploit containing private data.

NoCap is a single-user local workbench. It binds to `127.0.0.1` by default; Compose publishes only on loopback. It has no multi-user authentication, tenant separation or document ACLs. Do not expose it directly to the internet.

Uploads accept UTF-8 `.md` and `.txt` only, with a 200 KB file limit and a 100-document workspace limit. Filenames are metadata, never filesystem paths. Documents and traces live in a local SQLite file. Removing a source does not remove saved trace excerpts. To remove all stored content, stop the server and remove your `data/nocap.sqlite3` file and any exports or backups.

The browser has no API keys. Keys stay in server environment variables. Requests to hosted Jev send the question and selected excerpts to the configured service. Laya and Ollama can also be remote if you configure their URLs. Logs do not deliberately include request bodies. JSON trace exports do include questions and source excerpts.

Evidence text is untrusted. The prompts delimit data and request that models ignore embedded instructions; this is not a proof of injection resistance. Citation checks validate IDs, not the truth or semantic entailment of a claim. Decisions and thresholds can be wrong. This project does not certify factual accuracy or make autonomous high-stakes decisions.
