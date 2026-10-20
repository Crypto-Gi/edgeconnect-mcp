# Contributing

Thanks for helping. Issues and pull requests are both welcome.

## Reporting a problem

Open an [issue](https://github.com/Crypto-Gi/edgeconnect-mcp/issues) with the server version (the release tag you installed), your Orchestrator version, the tool call and the error. Never paste an API key, token, password or a full `.env`; replace addresses and names you don't want public.

For a security problem, don't post the details publicly: open an issue that only says you have a security report, and a private channel will be arranged.

## Pull requests

1. Branch from `main`.
2. Run the tests from the repository root. They use only the standard library, and they read `./.env` if one exists, so move your real `.env` out of the way first:

   ```bash
   PYTHONPATH=src python3 -m unittest discover -s tests
   ```

3. Keep the server dependency-free (standard library only, Python 3.9+).
4. Document only what you have tested. If a change touches how the server talks to an Orchestrator, say in the pull request which Orchestrator version you ran it against; if you could not run it against one, say that instead.
5. Guide skill changes: name only operations listed in `skills/edgeconnect-guide/tested-operations.tsv`, link official docs rather than copying them, and run `skills/edgeconnect-guide/scripts/check_links.py` (see the README).

CI runs the tests on Python 3.9 and 3.13 for every pull request, and both must pass before a merge.

By contributing you agree that your contribution is licensed under the [Apache License 2.0](LICENSE).
