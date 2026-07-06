# Feature Sample Puller

Pulls a random sample of N records per group value (e.g. per county, per
district, per category) from an ArcGIS hosted feature service, then exports
the results as a file geodatabase feature class, a CSV of selected fields, or
both.

Useful for quickly grabbing a representative test dataset from a large hosted
layer without exporting the whole thing.

## Requirements

- ArcGIS Pro installed and licensed on the machine running the script
- Run from the Python environment bundled with ArcGIS Pro (`arcgispro-py3`),
  since it depends on `arcpy`
- Signed in to ArcGIS Pro under an account with read access to the target
  feature service, since authentication uses `GIS("Pro")`

## Setup

1. Copy `config.example.json` to `config.json` in the same folder as the
   script.
2. Edit `config.json`:

| Key | Description |
|---|---|
| `serviceUrl` | REST endpoint for the layer, including the layer index (e.g. `.../FeatureServer/0`) |
| `groupField` | Field used to split records into groups before sampling (e.g. `county`, `district`, `category`) |
| `groupValues` | List of group values to sample from |
| `recordsPerGroup` | Number of random records to pull per group value |
| `exportFields` | List of field names to include in the CSV output |
| `outputGdb` | File geodatabase name for the feature class output |
| `outputFeatureClass` | Feature class name inside `outputGdb` |
| `outputCsv` | CSV filename for the attribute-only output |
| `writeGdb` | `true`/`false`, whether to export the feature class |
| `writeCsv` | `true`/`false`, whether to export the CSV |

## Running

From the ArcGIS Pro Python Command Prompt (or Pro's Python window):

```
python getFeatureSample.py
```

Outputs are written to the same folder as the script:
- `<outputGdb>/<outputFeatureClass>` (if `writeGdb` is `true`)
- `<outputCsv>` (if `writeCsv` is `true`)

A timestamped log file is also written to a `logs` subfolder.

## Notes

- Sampling is randomized per group value, using `random.sample()` against the
  full set of object IDs matching that group, so it's a true random draw
  rather than just the first N records returned.
- If a group value has fewer records available than `recordsPerGroup`, the
  script pulls what's available and logs a warning rather than failing.
- If a group value has zero matching records, the script logs a warning and
  moves on to the next group.
