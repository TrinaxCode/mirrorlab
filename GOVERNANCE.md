# Governance

MirrorLab is a small project with a simple structure, written down so that anyone can
understand how decisions are made and how to take part in them.

## Roles

- **Maintainers** merge pull requests, cut releases and have the final say on direction. Today
  that is [@TrinaxCode](https://github.com/TrinaxCode), the project's creator.
- **Contributors** are everyone who sends an issue, a pull request, a translation or a review.
  There is no contributor agreement to sign (see [Licence of contributions](CONTRIBUTING.md#licence-of-contributions)).

## How decisions are made

1. Small changes (bug fixes, docs, tests) are decided in the pull request.
2. Larger changes (new features, new dependencies, changes to the privacy guarantees or the
   licence boundary) start as an issue or a Discussion, so the idea is discussed before the code
   is written.
3. Maintainers aim for consensus. When there is none, the maintainers decide and write the
   reason down in the issue or in an [ADR](docs/adr/).

## What does not change without a very good reason

These are the promises users rely on. A change to any of them needs a public proposal and a
changelog entry that says so plainly:

- Nothing leaves the user's machine; the only network access is the one-time model download.
- Background effects fail closed, and a closed shutter shows no camera pixels.
- The source code stays under an OSI-approved licence, and the optional GPL dependency
  (`pyvirtualcam`) stays out of the default install.

## Becoming a maintainer

Contributors who have landed several substantial changes, reviewed other people's work and
shown good judgement on the promises above can be invited to become maintainers. Ask in a
Discussion if you are interested.

## Releases

Releases follow [Semantic Versioning](https://semver.org) and are described in
[docs/RELEASING.md](docs/RELEASING.md). Every release is built by CI from a tag, with checksums
and build provenance, so anyone can check that a download matches the source.
