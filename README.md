<p align="center">
  <img src="https://codtube.tv/static/images/ctube_navbar.png" alt="CoDTUBE" />
</p>

# CoDTUBE OBS Uploader

Upload clips directly from OBS Studio to CoDTUBE with a dedicated upload token.

## Release status

- Version: `1.0.0`
- Status: `Public recorder uploader build`
- Supported games in this release: `Call of Duty 1`, `Call of Duty 2`, `Call of Duty 4`

This script is meant for a clean recorder workflow:

- pick a local clip file
- choose the game
- add title, map, weapon and tags
- send the clip straight to CoDTUBE

The uploader is fixed to the live CoDTUBE instance at `https://codtube.tv`.

## Current release scope

The current public version supports:

- `Call of Duty 1`
- `Call of Duty 2`
- `Call of Duty 4`

## Features

- uploads a local clip from OBS to CoDTUBE
- uses a separate CoDTUBE OBS upload token
- supports clip metadata like title, map, weapon and tags
- keeps form values inside OBS between sessions
- shows clear success and error status messages
- can optionally clear the text fields after a successful upload

## Requirements

- OBS Studio with Python scripting enabled
- a CoDTUBE account
- a valid OBS upload token from your CoDTUBE dashboard

## Setup

1. Open OBS and go to `Tools -> Scripts`.
2. Add `codtube_obs_uploader.py`.
3. Paste your `Upload token`.
4. Pick your clip file.
5. Choose the game and fill in the clip details.
6. Click `Upload to CoDTUBE`.

## Field overview

- `Upload token`
  A dedicated token from `Dashboard -> Profile settings -> OBS upload token`.

- `Game`
  This release currently supports `cod1`, `cod2` and `cod4`.

- `Title`
  Required. This becomes the public clip title on CoDTUBE.

- `Map`, `Weapon`, `Tags`
  Optional extra metadata for the upload.

- `Clip file`
  The local video file OBS should upload.

- `Clear text fields after successful upload`
  Resets the clip fields after a successful upload so the next upload starts clean.

## Notes

- The player name is resolved server-side from your CoDTUBE account.
- If you regenerate your OBS upload token in CoDTUBE, the old token stops working immediately.
- `Reset form` clears the clip fields and resets the upload state.
- OBS usually keeps script values between restarts.

## Common issues

- `Missing upload token.`
  Add your OBS upload token first.

- `Choose a valid game.`
  The selected game is not supported by the current release.

- `Choose a clip file first.`
  No local file is selected yet.

- `Selected clip file does not exist.`
  The selected file was moved, renamed or deleted.

- `Could not reach CoDTUBE: ...`
  CoDTUBE is offline, unreachable or blocked by your connection.

- `Upload was rejected.`
  CoDTUBE received the request but refused the upload. Check the returned server message and your token.

## License note

This OBS helper script is intended as a CoDTUBE community tool.

If you publish it on GitHub, add the license you want for the script repository itself so reuse is clearly defined from day one.
