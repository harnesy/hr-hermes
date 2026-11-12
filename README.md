# hr-hermes

A plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent) that hires an AI employee from
[hr.harnsy.dev](https://hr.harnsy.dev), the catalog of AI employees, as a Hermes **profile** of its own.

An employee is a role with a character: who it is, how it decides and speaks, its job, and the skills it works with.
In Hermes one employee is one profile: its own `SOUL.md`, its own skills, its own memory and sessions. You talk to
`accountant` as a separate agent. Your own profile and its `SOUL.md` are never touched.

The plugin adds the command `hermes harnsy-hr` and the chat command `/harnsy-hr`. It registers no tools and no hooks:
the model never calls it, it runs only when you do. It was built and tried with Hermes Agent v0.23.1.

## Install

You need Hermes Agent v0.23.1 and `git` on the machine.

```
hermes plugins install harnesy/hr-hermes --enable
```

This installs the current `main`. To stay on one release, add `--ref <40-character commit>`: Hermes takes a full
commit there, not a tag, and each release on
[the releases page](https://github.com/harnesy/hr-hermes/releases) names its commit. Hermes warns that the source is
not from its catalog. The plugin never updates itself: a new version reaches you only when you install again.

From a clone of this repository, both of these were tried and work:

```
hermes plugins install file:///path/to/hr-hermes --ref <40-character commit> --enable
```

or copy the folder to `~/.hermes/plugins/harnsy-hr/` and run `hermes plugins enable harnsy-hr`.

It needs nothing installed: the standard library, and the `cryptography` package that Hermes Agent ships.

## First hire

```
hermes harnsy-hr search accountant          find an employee
hermes harnsy-hr show harnsy/accountant     the card, what it needs, the files, the notice
hermes harnsy-hr hire harnsy/accountant     asks, then Hermes asks its own install question
hermes -p accountant setup                  pick its model once: a new profile has no model settings
hermes -p accountant chat                   talk to it
```

Instead of the `setup` dialogue, the model can be set in three lines, here for an OpenAI-compatible address:

```
hermes -p accountant config set model.provider custom
hermes -p accountant config set model.base_url <address>
hermes -p accountant config set model.default <model>
```

These lines were run as written on a clean Hermes Agent v0.23.1 on Linux, with the plugin installed from GitHub: the
hire at a terminal, answering both questions, and again with `--yes`; the three `config set` lines in place of
`setup`; one question with `chat -q`. The employee answers in its role, and its whole `SOUL.md` reached the model.
Not run: Windows, macOS, the `setup` dialogue.

## Commands

| Command | What it does |
|---|---|
| `hermes harnsy-hr search [words]` | Find an employee by a role, a skill or a need. `--department`, `--limit`. |
| `hermes harnsy-hr show <id>` | Its card, what it needs, every file it brings and its notice. Writes no employee file. |
| `hermes harnsy-hr hire <id>` | Install it as a profile beside your own. `--name <name>` for another profile name, `--alias` to pass `--alias` on to Hermes, `--yes` for scripts. |
| `hermes harnsy-hr update <name>` | Bring a hired employee to the catalog's current version. Your settings, memory and `.env` in the profile stay. |
| `hermes harnsy-hr list` | The employees hired on this machine. |
| `hermes harnsy-hr fire <name>` | Delete a hired employee's profile, then the files this plugin kept for it. Hermes asks you to type the profile's name first (`--yes` answers beforehand); the profile's memory and sessions go with it. |

An id is `<publisher>/<name>`, for example `harnsy/accountant`.

`hire` shows the card, what the employee needs, the list of files and the full notice, and asks you. After your yes it
builds the profile's files and runs Hermes' own `hermes profile install`, which shows what it installs and asks you
once more. `--yes` answers both beforehand. Then:

```
hermes -p <name> setup     pick its model once: a new profile has no model settings
hermes -p <name> chat      talk to it
```

A profile of that name that already exists is never replaced: `hire` stops and asks for `--name`.

In a chat, `/harnsy-hr search <words>`, `/harnsy-hr show <id>` and `/harnsy-hr list` answer in place (`search` and
`show` fetch the catalog and write the feed number to `state.json`, from the process that serves the chat). For
`hire`, `update` and `fire` the chat command answers with the terminal command to run: they ask you questions, and a
chat command runs where nobody may be at a terminal. Every chat answer is one code block, so a link or a mention in a
publisher's text is shown as written and not made by the bot.

## What is checked on your machine

Before anything is written, on every `search`, `show`, `hire` and `update`:

- the catalog's feed carries a valid Ed25519 signature over its exact bytes, by the catalog's public key, which is
  built into the plugin (`c1`, in `harnsy_hr/keys.py`); a key the plugin does not know stops it with «update the
  plugin»;
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

One of the copied patterns lists its alternatives in another order than Hermes does (the same texts match), so that
Hermes' scanner of plugin code does not misread the plugin's own file as a command that dumps the environment; the
file says so where the pattern is.

What is not checked: what an employee's text says. It is a prompt written by its publisher; read `show` before you
hire. What the plugin prints of it (the card, the notice, file names) is printed without control characters and
without the characters nobody sees; the files are saved as published.

## What it does on your machine

- **Network.** `GET` requests to `https://hr.harnsy.dev` only: the feed, its signature, and the file of the employee
  you asked for. The request carries `User-Agent: hr-hermes/<version>` and nothing else of yours. The catalog's site
  logs requests like any site (address, time, path, `User-Agent`). No telemetry, no other host. The plugin connects
  straight to the catalog: a proxy named in the environment (`https_proxy`, `http_proxy`) is not used, so behind a
  proxy-only network the plugin does not work. No redirect is followed. Each step waits at most 20 seconds, and a
  file that has not arrived whole 60 seconds after its request is given up (the clock is looked at between the
  pieces of the file).
- **Files.** It writes to its own folder under the Hermes home, `~/.hermes/harnsy-hr/`: `state.json` (the newest feed
  number seen, and what you hired) and `profiles/<name>/` (the files of each hired employee; they stay there,
  `hermes profile update` reads them again). Hermes then copies them into the profile folder,
  `~/.hermes/profiles/<name>/`. Signatures are checked by `hermes harnsy-hr hire` and `hermes harnsy-hr update`
  only: `hermes profile update <name>` run directly installs whatever that kept folder holds at that moment, with no
  signature check then. The plugin reads that profile's `distribution.yaml` and the files it installed, to
  see whether Hermes finished. It never reads `.env`, `auth.json` or any other credential store.
- **One child process.** `hermes profile install`, `hermes profile update` or `hermes profile delete`, started with
  an argument list (no shell), at your terminal, so Hermes asks its own question. Nothing else is started. The
  Hermes started is the one that is running, by its own interpreter: `<the running Python> -P -m hermes_cli.main …`.
  Nothing is looked up on `PATH` and nothing is taken from the current folder (`-P` keeps that folder out of
  Python's search for modules), so a `hermes`, a `hermes.bat` or a `hermes_cli/` lying in the folder you stand in is
  never what starts. When the running Hermes cannot be found this way, nothing is started.
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

## Test catalogs

For test stands only. Two environment variables change where the catalog is fetched from and which key it is checked
with: `HARNSY_HR_FEED` (an address) and `HARNSY_HR_PUB` (`<kid>:<base64 of the raw public key>`; it replaces the
built-in key). Hermes fills the environment from `<Hermes home>/.env`, so a variable alone is not your word that a
test catalog is wanted. That is why there is a flag:

- A test catalog is read only when the command line says `--test-catalog` as well (`search`, `show`, `hire`,
  `update`). With a variable set and no flag, the command refuses before anything is fetched or written and names the
  variable; unset it to read hr.harnsy.dev. With the flag and no variable it refuses too.
- Never in a chat: `/harnsy-hr search` and `/harnsy-hr show` refuse while a variable is set. `list` and `fire` read
  no catalog and work as always.
- With the flag, every command first prints a line saying that a test catalog is in use, and the question `hire` and
  `update` ask names the test catalog's address and key id and says that it is not hr.harnsy.dev. `--yes` together
  with `--test-catalog` is allowed and skips that question: both are words of the command line, and stands are
  scripted.
- `HARNSY_HR_FEED` with plain `http` is taken only for this machine itself (`127.0.0.1`, `[::1]`, `localhost`); any
  other address needs `https`.
- The feed number of a test catalog is kept in `state.json` under `test:<kid>`, apart from the built-in key's: a
  test run never reads or changes the number kept for `c1`, so a stand cannot lock the real catalog out.

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
