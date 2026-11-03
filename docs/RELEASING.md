# Releasing

Releases are cut from `main` by pushing a version tag. CI builds, tests and publishes; nobody
uploads binaries by hand.

## Checklist

1. `main` is green (CI) and `CHANGELOG.md` has a section for the version, with the date.
2. The version is bumped in `src/mirrorlab/version.py`, `pyproject.toml` and `CITATION.cff`.
   The release workflow refuses a tag that does not match `version.py`.
3. Optional dry run: *Actions → Release → Run workflow* builds the installers as artifacts
   without publishing anything.
4. Tag and push:

   ```bash
   git tag -a vX.Y.Z -m "MirrorLab X.Y.Z"
   git push origin vX.Y.Z
   ```

5. The workflow builds Windows, macOS and Linux, runs the self-test and a window smoke test on
   each, attaches the installers, `SHA256SUMS.txt` and the release notes (taken from the
   changelog) to a GitHub release.
6. Deploy the website if it changed: `npm run build` in `web/`, then
   `firebase deploy --only hosting` (or let the *Deploy web* workflow do it).

## Verifying a download

```bash
sha256sum --check --ignore-missing SHA256SUMS.txt
gh attestation verify MirrorLab-<version>-linux-x86_64.tar.gz --repo TrinaxCode/mirrorlab
```

The second command checks the build provenance: that the file was produced by this
repository's release workflow from the tagged commit.

## If a release is bad

Do not move or delete a published tag. Mark the release as a pre-release or edit its notes with
the problem, fix forward, and publish the next patch version.
