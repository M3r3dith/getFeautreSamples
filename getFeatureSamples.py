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


def getSample(gis_GTG, serviceUrl, groupField, groupValues, recordsPerGroup, needsGeometry):
    """
    Connects to the feature service and pulls a random sample of
    recordsPerGroup records per group value. Returns a single combined
    spatially enabled dataframe.
    """
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
            return_geometry=needsGeometry
        )

        groupSdf = featureSet.sdf

        if groupSdf.empty:
            logging.warning(f"No records returned for group: {groupValue}")
            continue

        logging.info(f"Retrieved {len(groupSdf)} records for group: {groupValue}")
        sampleFrames.append(groupSdf)

    if not sampleFrames:
        logging.warning("No records retrieved for any group.")
        return None

    combinedSdf = pd.concat(sampleFrames, ignore_index=True)
    logging.info(f"Combined sample contains {len(combinedSdf)} total records")

    return combinedSdf


def exportToGdb(sdf, outputGdb, outputFeatureClass):
    """
    Exports a spatially enabled dataframe to a file geodatabase feature
    class, creating the geodatabase first if it doesn't already exist.
    """
    outputGdbPath = f"{scriptDirectory}/{outputGdb}"
    if not arcpy.Exists(outputGdbPath):
        arcpy.management.CreateFileGDB(scriptDirectory, outputGdb)
        logging.info(f"Created file geodatabase: {outputGdbPath}")

    outputPath = f"{outputGdbPath}/{outputFeatureClass}"
    sdf.spatial.to_featureclass(location=outputPath, overwrite=True)
    logging.info(f"Exported sample feature class to: {outputPath}")


def exportToCsv(sdf, exportFields, outputCsv):
    """
    Exports selected fields from a dataframe to a CSV file.
    """
    csvSdf = sdf[exportFields].copy()

    csvPath = f"{scriptDirectory}/{outputCsv}"
    csvSdf.to_csv(csvPath, index=False)
    logging.info(f"Exported CSV summary to: {csvPath}")


def runFeatureSample():
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

    combinedSdf = getSample(
        gis_GTG=gis_GTG,
        serviceUrl=serviceUrl,
        groupField=groupField,
        groupValues=groupValues,
        recordsPerGroup=recordsPerGroup,
        needsGeometry=writeGdb
    )

    if combinedSdf is None:
        logging.warning("No sample data retrieved. Exiting without export.")
        return

    if writeGdb:
        exportToGdb(combinedSdf, outputGdb, outputFeatureClass)

    if writeCsv:
        exportToCsv(combinedSdf, exportFields, outputCsv)


if __name__ == "__main__":
    try:
        runFeatureSample()
    except Exception as e:
        logging.error(f"Script failed: {e}")
