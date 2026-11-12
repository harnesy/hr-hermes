# hr-hermes

A plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent) that hires an AI employee from
[hr.harnsy.dev](https://hr.harnsy.dev), the catalog of AI employees, as a Hermes **profile** of its own.

An employee is a role with a character: who it is, how it decides and speaks, its job, and the skills it works with.
In Hermes one employee is one profile: its own `SOUL.md`, its own skills, its own memory and sessions. You talk to
`accountant` as a separate agent. Your own profile and its `SOUL.md` are never touched.

The plugin adds the command `hermes harnsy-hr` and the chat command `/harnsy-hr`. It registers no tools and no hooks:
the model never calls it, it runs only when you do. It was built and tried with Hermes Agent v0.23.1.

> **Status.** This version holds no catalog key yet (`harnsy_hr/keys.py` has an empty slot for it), so every command
> that needs the catalog stops with one sentence saying so. It starts working with the release that carries the key.

## Install

```
hermes plugins install harnesy/hr-hermes --ref <40-character commit> --enable
```

This line is valid once a release commit exists; none does yet. Hermes installs a plugin at an exact commit, and the
plugin never updates itself: a new version reaches you only when you install a newer commit.

From a clone of this repository, both of these were tried and work:

```
hermes plugins install file:///path/to/hr-hermes --ref <40-character commit> --enable
```

or copy the folder to `~/.hermes/plugins/harnsy-hr/` and run `hermes plugins enable harnsy-hr`.

It needs nothing installed: the standard library, and the `cryptography` package that Hermes Agent ships.

## Commands

| Command | What it does |
|---|---|
| `hermes harnsy-hr search [words]` | Find an employee by a role, a skill or a need. `--department`, `--limit`. |
| `hermes harnsy-hr show <id>` | Its card, what it needs, every file it brings and its notice. Writes no employee file. |
| `hermes harnsy-hr hire <id>` | Install it as a profile beside your own. `--name <name>` for another profile name, `--alias` to pass `--alias` on to Hermes, `--yes` for scripts. |
| `hermes harnsy-hr update <name>` | Bring a hired employee to the catalog's current version. Your settings, memory and `.env` in the profile stay. |
| `hermes harnsy-hr list` | The employees hired on this machine. |
| `hermes harnsy-hr fire <name>` | Delete a hired employee's profile, then the files this plugin kept for it. |

An id is `<publisher>/<name>`, for example `harnsy/accountant`.

`hire` shows the card, what the employee needs, the list of files and the full notice, and asks you. After your yes it
builds the profile's files and runs Hermes' own `hermes profile install`, which shows what it installs and asks you
once more. `--yes` answers both beforehand. Then:

```
hermes -p <name> setup     pick its model once: a new profile has no model settings
hermes -p <name> chat      talk to it
```

A profile of that name that already exists is never replaced: `hire` stops and asks for `--name`.

In a chat, `/harnsy-hr search <words>`, `/harnsy-hr show <id>` and `/harnsy-hr list` answer in place. For `hire`,
`update` and `fire` the chat command answers with the terminal command to run: they ask you questions, and a chat
command runs where nobody may be at a terminal.

## What is checked on your machine

Before anything is written, on every `search`, `show`, `hire` and `update`:

- the catalog's feed carries a valid Ed25519 signature over its exact bytes, by a key built into the plugin; a key
  the plugin does not know stops it with «update the plugin»;
- the feed is of the known version, has not expired, and is not older than one this machine has already seen;
- the employee's file is on the catalog's own host, and has the size and the SHA-256 the signed feed names, before
  it is opened;
- the file unpacks within fixed limits (128 entries, 8 MB), with no name that leaves its folder and plain files only;
- every file in it has the hash its manifest names, and the manifest carries the catalog's signature for this
  employee and this version; a withdrawn version is not offered;
- ids, versions and file names have the catalog's own form, before any of them becomes a path, a command argument or
  a line of YAML; every file is written inside the employee's folder and nowhere else.

Any failure stops the command with the reason, and nothing is written.

One more check is about Hermes, not about safety. Hermes leaves a profile's whole `SOUL.md` out when its own scanner
for profile files matches a pattern in it (ordinary job wording can match). The plugin runs the same patterns over the
`SOUL.md` it is about to install and refuses the hire, naming the pattern, because that profile would run without its
role. This protects you from nothing: it only tells whether the employee can work in Hermes.

What is not checked: what an employee's text says. It is a prompt written by its publisher; read `show` before you
hire.

## What it does on your machine

- **Network.** `GET` requests to `https://hr.harnsy.dev` only: the feed, its signature, and the file of the employee
  you asked for. The request carries `User-Agent: hr-hermes/<version>` and nothing else of yours. The catalog's site
  logs requests like any site (address, time, path, `User-Agent`). No telemetry, no other host.
- **Files.** It writes to its own folder under the Hermes home, `~/.hermes/harnsy-hr/`: `state.json` (the newest feed
  number seen, and what you hired) and `profiles/<name>/` (the files of each hired employee; they stay there,
  `hermes profile update` reads them again). Hermes then copies them into the profile folder,
  `~/.hermes/profiles/<name>/`. The plugin reads that profile's `distribution.yaml` and the files it installed, to
  see whether Hermes finished. It never reads `.env`, `auth.json` or any other credential store.
- **One child process.** `hermes profile install`, `hermes profile update` or `hermes profile delete`, started with
  an argument list (no shell), at your terminal, so Hermes asks its own question. Nothing else is started.
- **Scripts.** Some employees bring scripts in their skills. The plugin saves them as plain files and never runs
  them.
- **No self-update.** The plugin never fetches or replaces its own code.

A profile holds:

```
SOUL.md                      who the employee is and its job
skills/<publisher>/<skill>/  its skills, byte for byte as published, and its casebook as the skill persona-casebook
NOTICE.md                    licence, source, credits: keep it with the employee
distribution.yaml            name, version, author, licence, and where Hermes installed it from
```

and the folders Hermes makes for every profile (memory, sessions, logs and so on). There is no `config.yaml`: the
profile's model settings are yours. When a newer version of an employee drops a skill, Hermes keeps the old skill's
folder in the profile; `update` names it so you can remove it.

For test stands only, two environment variables change where the catalog is fetched from and which key it is checked
with: `HARNSY_HR_FEED` and `HARNSY_HR_PUB`. When either is set, every command first prints a line saying that a test
catalog is in use.

## Licences

The code in this repository is under the MIT licence (`LICENSE`). The patterns in `harnsy_hr/hermesscan` are copied
from Hermes Agent, which is under the MIT licence too: its notice is in that folder and in `THIRD_PARTY_LICENSES`
(see `NOTICE`). The employees are not part of this repository. Each has its own licence, most often CC BY 4.0, and
arrives with a `NOTICE.md` that names its author, licence, source and the works it is built on: keep that file with
the employee. An employee's text is under the licence its `NOTICE.md` names, not under this repository's MIT licence.
Each skill keeps its own `LICENSE` file where it has one.

This project is not affiliated with or endorsed by OpenClaw, Nous Research (Hermes Agent), Anthropic, OpenAI or the
MCP project; their names are used only to say what it works with.

## Tests

```
python -m unittest discover -s tests -t .
```

with Python 3.14 and the `cryptography` package. The employees under `tests/testdata` are made up for the tests.
