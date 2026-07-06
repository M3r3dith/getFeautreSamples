import os
import sys
import json
import random
import logging
from datetime import date
import arcpy
import pandas as pd
from arcgis.gis import GIS
from arcgis.features import FeatureLayer

# Base path variables
scriptDirectory = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
dateNow = date.today().strftime("%Y-%m-%d")

# Initiate logging
logDirectory = f"{scriptDirectory}/logs"
logFile = f"{logDirectory}/getFeatureSample_{dateNow}.log"

os.makedirs(logDirectory, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
    handlers=[logging.FileHandler(logFile), logging.StreamHandler(sys.stdout)]
)
logging.info(f"\n\n===============================\nStarting script: {scriptDirectory}")

arcpy.env.overwriteOutput = True


def getFeatureSample():
    """
    Pulls a random sample of N records per group value (e.g. per county, per
    district, per category) from a hosted feature service, then exports the
    results as a file geodatabase feature class and/or a CSV of selected
    fields.

    Configure via config.json:
      - serviceUrl:      REST endpoint for the layer, ending in a layer index
      - groupField:      field used to split records into groups (e.g. "county")
      - groupValues:     list of group values to sample from (e.g. county names)
      - recordsPerGroup: number of random records to pull per group value
      - exportFields:    list of field names to include in the CSV output
      - outputGdb:        file geodatabase name for the feature class output
      - outputFeatureClass: feature class name inside outputGdb
      - outputCsv:        CSV filename for the attribute-only output
      - writeGdb:         true/false, whether to export the feature class
      - writeCsv:         true/false, whether to export the CSV
    """
    configPath = f"{scriptDirectory}/config.json"
    with open(configPath, "r") as configFile:
        config = json.load(configFile)

    serviceUrl = config["serviceUrl"]
    groupField = config["groupField"]
    groupValues = config["groupValues"]
    recordsPerGroup = config["recordsPerGroup"]
    exportFields = config["exportFields"]
    outputGdb = config["outputGdb"]
    outputFeatureClass = config["outputFeatureClass"]
    outputCsv = config["outputCsv"]
    writeGdb = config["writeGdb"]
    writeCsv = config["writeCsv"]

    gis_GTG = GIS("Pro")
    logging.info("Authenticated to Portal via GIS(\"Pro\")")

    featureLayer = FeatureLayer(serviceUrl, gis=gis_GTG)
    logging.info(f"Connected to feature layer: {serviceUrl}")

    oidField = featureLayer.properties.objectIdField
    logging.info(f"Detected object ID field: {oidField}")

    sampleFrames = []

    for groupValue in groupValues:
        whereClause = f"{groupField} = '{groupValue}'"
        logging.info(f"Finding candidate {oidField} values for group: {groupValue}")

        idResult = featureLayer.query(
            where=whereClause,
            out_fields=oidField,
            return_geometry=False
        )

        candidateIds = [feature.attributes[oidField] for feature in idResult.features]

        if not candidateIds:
            logging.warning(f"No candidate records found for group: {groupValue}")
            continue

        sampleSize = min(recordsPerGroup, len(candidateIds))
        sampledIds = random.sample(candidateIds, sampleSize)
        logging.info(f"Randomly sampled {sampleSize} {oidField} values for group: {groupValue}")

        idList = ", ".join(str(oid) for oid in sampledIds)
        sampleWhereClause = f"{oidField} IN ({idList})"

        featureSet = featureLayer.query(
            where=sampleWhereClause,
            out_fields="*",
            return_geometry=writeGdb
        )

        groupSdf = featureSet.sdf

        if groupSdf.empty:
            logging.warning(f"No records returned for group: {groupValue}")
            continue

        logging.info(f"Retrieved {len(groupSdf)} records for group: {groupValue}")
        sampleFrames.append(groupSdf)

    if not sampleFrames:
        logging.warning("No records retrieved for any group. Exiting without export.")
        return

    combinedSdf = pd.concat(sampleFrames, ignore_index=True)
    logging.info(f"Combined sample contains {len(combinedSdf)} total records")

    if writeGdb:
        outputGdbPath = f"{scriptDirectory}/{outputGdb}"
        if not arcpy.Exists(outputGdbPath):
            arcpy.management.CreateFileGDB(scriptDirectory, outputGdb)
            logging.info(f"Created file geodatabase: {outputGdbPath}")

        outputPath = f"{outputGdbPath}/{outputFeatureClass}"
        combinedSdf.spatial.to_featureclass(location=outputPath, overwrite=True)
        logging.info(f"Exported sample feature class to: {outputPath}")

    if writeCsv:
        csvSdf = combinedSdf[exportFields].copy()

        csvPath = f"{scriptDirectory}/{outputCsv}"
        csvSdf.to_csv(csvPath, index=False)
        logging.info(f"Exported CSV summary to: {csvPath}")


if __name__ == "__main__":
    try:
        getFeatureSample()
    except Exception as e:
        logging.error(f"Script failed: {e}")
