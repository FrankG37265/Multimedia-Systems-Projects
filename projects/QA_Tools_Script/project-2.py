import argparse
import string
import pymongo
import pandas as pd
import numpy as np
import csv
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from dateutil.parser import parse

nltk.download('punkt')
nltk.download('stopwords')

stop_words = set(stopwords.words('english'))
stop_words.update(string.punctuation)

parser = argparse.ArgumentParser(description="Load and parse exports from QA XLSX into a MongoDB database.")
parser.add_argument("--files", metavar="FILE", nargs="+", type=str, help="The XLSX file(s) to insert into MongoDB.")
parser.add_argument("--testuser", type=str, help="The test owner to search for in the database.")
parser.add_argument("--frankgonzalez", action="store_true", help="Run the Frank Gonzalez search algorithm to find similar bugs based on test case, expected result, and actual result.")
parser.add_argument("--build", type=str, help="The build number to search for in the database.")
parser.add_argument("--repeatable_blocker", action="store_true", help="Find bugs that are both repeatable and blockers.")
parser.add_argument("--not_repeatable_blocker", action="store_true", help="Find bugs that are neither repeatable nor blockers.")
parser.add_argument("--repeatable", action="store_true", help="Find all repeatable bugs.")
parser.add_argument("--blocker", action="store_true", help="Find all blocker bugs.")
args = parser.parse_args()

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["project2"]
headers = ["Test #", "Build #", "Category", "Test Case", "Expected Result", "Actual Result", "Repeatable?", "Blocker?", "Test Owner"]

# Load data into collections based on the files
if args.files:
    for file in args.files:
        datasample = pd.read_excel(file)
        records = datasample.to_dict(orient="records")

        # This just grabs the c1 or c2 from the filename
        mycol = mydb[file.split('_')[2].split('.')[0]]

        x = mycol.insert_many(records)
        print(f"Inserted {len(x.inserted_ids)} records from {file} into MongoDB collection {mycol.name}.")

# Function to remove common words from a text string
def remove_common_words(text):
    unfiltered_words = word_tokenize(text.lower())
    filtered_words = [word for word in unfiltered_words if word not in stop_words]
    return filtered_words

class DBCalls:
    def __init__(self):
        self.client = pymongo.MongoClient("mongodb://localhost:27017/")
        self.db = self.client["project2"]

    # List all work done by Test Owner from both collections and write to a CSV file
    def find_test_owner(self, test_owner, headers):
        for collection in self.db.list_collection_names():
            result = list(self.db[collection].find({"Test Owner": test_owner}))
            if result:
                with open(f"{test_owner}.csv", "a", newline="") as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=headers)
                    writer.writeheader()
                    for record in result:
                        record.pop("_id", None)  # Remove the MongoDB-generated _id field
                        writer.writerow(record)
                print(f"Found {len(result)} records for test owner '{test_owner}' in collection '{collection}'. Results written to '{test_owner}.csv'.")
            else:
                print(f"No records found for test owner '{test_owner}'")

    def find_repeatable(self):
        for collection in self.db.list_collection_names():
            result = list(self.db[collection].find({"Repeatable?": {"$in": ["Yes", "yes", "YES", "Y", "y"]}}))
            if result:
                with open("repeatable.txt", "a") as txtfile:
                    for record in result:
                        txtfile.write(f"Test # {record.get('Test #', 'N/A')}, Build # {record.get('Build #', 'N/A')}: {record.get('Test Case', 'N/A')}\n")
                print(f"Found {len(result)} repeatable tests in collection '{collection}'. Results written to 'repeatable.txt'.")
            else:
                print(f"No repeatable bugs found in collection '{collection}'.")

    def find_blocker(self):
        for collection in self.db.list_collection_names():
            result = list(self.db[collection].find({"Blocker?": {"$in": ["Yes", "yes", "YES", "Y", "y"]}}))
            if result:
                with open("blocker.txt", "a") as txtfile:
                    for record in result:
                        txtfile.write(f"Test # {record.get('Test #', 'N/A')}, Build # {record.get('Build #', 'N/A')}: {record.get('Test Case', 'N/A')}\n")
                print(f"Found {len(result)} blocker tests in collection '{collection}'. Results written to 'blocker.txt'.")
            else:
                print(f"No blocker bugs found in collection '{collection}'.")

    def find_repeat_and_blocker(self, override):
        result = []
        for collection in self.db.list_collection_names():

            # If override is False, find bugs that are both repeatable and blockers. If override is True, find bugs that are neither repeatable nor blockers.
            if override == False:
                docs = list(self.db[collection].find({"$and": [{"Repeatable?": {"$in": ["Yes", "yes", "YES", "Y", "y"]}}, {"Blocker?": {"$in": ["Yes", "yes", "YES", "Y", "y"]}}]}))
            else:
                docs = list(self.db[collection].find({"$and": [{"Repeatable?": {"$in": ["No", "no", "NO", "N", "n"]}}, {"Blocker?": {"$in": ["No", "no", "NO", "N", "n"]}}]}))
                result.extend(docs)
                return result
            if docs:
                result.extend(docs)
                with open("repeatable_blocker.txt", "a") as txtfile:
                    for record in docs:
                        txtfile.write(f"Test # {record.get('Test #', 'N/A')}, Build # {record.get('Build #', 'N/A')}: {record.get('Test Case', 'N/A')}\n")
                print(f"Found {len(docs)} bugs that are both repeatable and blockers in collection '{collection}'. Results written to 'repeatable_blocker.txt'.")
            else:
                print(f"No bugs found that are both repeatable and blockers in collection '{collection}'.")

        return result

    def find_build(self, build_number):
        for collection in self.db.list_collection_names():
            result = list(self.db[collection].find({"Build #": build_number}))
            if result:
                with open(f"build_{build_number}.txt", "a") as txtfile:
                    for record in result:
                        txtfile.write(f"Test # {record.get('Test #', 'N/A')}, Test Owner: {record.get('Test Owner', 'N/A')}, Test Case: {record.get('Test Case', 'N/A')}\n")
                print(f"Found {len(result)} tests for build number '{build_number}' in collection '{collection}'. Results written to 'build_{build_number}.txt'.")
            else:
                print(f"No records found for build number '{build_number}'")
            
    def frankgonzalezsearch(self):
        bugs = self.find_repeat_and_blocker(override=True)
        i = 0
        
        with open("LogicCall.csv", "w", newline="") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=["Category", "Test Case", "Expected Result", "Actual Result", "Total Builds", "Build #s"])
                writer.writeheader()

        while i < len(bugs):

            bug = bugs[i]
            bugcounter = 1
            builds = [bug.get("Build #", "N/A")]
            case = remove_common_words(str(bug.get("Test Case", "")))
            expected = remove_common_words(str(bug.get("Expected Result", "")))
            actual = remove_common_words(str(bug.get("Actual Result", "")))

            for nextbug in bugs[i+1:]:
                nextcase = remove_common_words(str(nextbug.get("Test Case", "")))
                nextexpected = remove_common_words(str(nextbug.get("Expected Result", "")))
                nextactual = remove_common_words(str(nextbug.get("Actual Result", "")))

                if set(case) & set(nextcase) and set(expected) & set(nextexpected) and set(actual) & set(nextactual):
                    bugcounter += 1
                    builds.append(nextbug.get("Build #", "N/A"))
                    bugs.remove(nextbug)
            
            # Write results to a file
            if bugcounter > 2: # Only write to the file if there are more than 2 similar bugs found
                with open("LogicCall.csv", "a", newline="") as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=["Category", "Test Case", "Expected Result", "Actual Result", "Total Builds", "Build #s"])
                    writer.writerow({
                        "Category": bug.get("Category", "N/A"),
                        "Test Case": bug.get("Test Case", "N/A"),
                        "Expected Result": bug.get("Expected Result", "N/A"),
                        "Actual Result": bug.get("Actual Result", "N/A"),
                        "Total Builds": bugcounter,
                        "Build #s": ", ".join(str(build) for build in builds)
                    })

            i += 1

if args.testuser:
    DBCalls().find_test_owner(args.testuser, headers)

if args.repeatable:
    DBCalls().find_repeatable()

if args.blocker:
    DBCalls().find_blocker()

if args.repeatable_blocker:
    DBCalls().find_repeat_and_blocker(override=False)

if args.not_repeatable_blocker:
    DBCalls().find_repeat_and_blocker(override=True)

if args.build:
    date = parse(args.build, fuzzy=True)
    DBCalls().find_build(date)

if args.frankgonzalez:
    DBCalls().frankgonzalezsearch()

