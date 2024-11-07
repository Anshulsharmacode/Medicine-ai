import re

import requests
import google.generativeai as genai
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Body
from pydantic import BaseModel
import astrapy
import json
from google.generativeai.types import HarmCategory, HarmBlockThreshold

load_dotenv()

app = FastAPI()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# Astra DB configuration
ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
ASTRA_DB_API_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT")

my_client = astrapy.DataAPIClient()
my_database = my_client.get_database(
    ASTRA_DB_API_ENDPOINT,
    token=ASTRA_DB_APPLICATION_TOKEN,
)

my_collection = my_database.get_collection("test")

class Query(BaseModel):
    text: str
    limit: int = 20

class Medicine:
    def __init__(self, medicine_name, composition, uses, sideeffects, image_url, manufacturer,
                 excellent_review_percentage, average_review_percentage, poor_review_percentage,
                 _id, price, packsizelabel, type):
        self.medicine_name = medicine_name
        self.composition = composition
        self.uses = uses
        self.sideeffects = sideeffects
        self.image_url = image_url
        self.manufacturer = manufacturer
        self.excellent_review_percentage = excellent_review_percentage
        self.average_review_percentage = average_review_percentage
        self.poor_review_percentage = poor_review_percentage
        self._id = _id
        self.price = price
        self.packsizelabel = packsizelabel
        self.type = type
    
    def to_dict(self):
        return {
            "medicine_name": self.medicine_name,
            "composition": self.composition,
            "uses": self.uses,
            "sideeffects": self.sideeffects,
            "image_url": self.image_url,
            "manufacturer": self.manufacturer,
            "excellent_review_percentage": self.excellent_review_percentage,
            "average_review_percentage": self.average_review_percentage,
            "poor_review_percentage": self.poor_review_percentage,
            "_id": self._id,
            "price": self.price,
            "packsizelabel": self.packsizelabel,
            "type": self.type,
        }

def load_medicines_from_url(url):
    response = requests.get(url)
    response.raise_for_status()  # Raise an error for bad responses
    medicines_data = response.json()
    return [Medicine(**med) for med in medicines_data]

def load_medicines_from_file(filepath):
    with open(filepath, 'r') as file:
        medicines_data = json.load(file)
    return [Medicine(**med) for med in medicines_data]

medicines = load_medicines_from_file('new_output_with_uuid.json')

def search_medicines(criteria, limit=20):
    results = []
    print(medicines[0])
    for medicine in medicines:
        # Check if all criteria match using case-insensitive substring search
        if all(value.lower() in getattr(medicine, key, "").lower() for key, value in criteria.items()):
            results.append(medicine.to_dict())

        if len(results) >= limit:
            break
            
    return results



def extract_json_from_text(input_text):
    # Find the text between curly brackets
    match = re.search(r'\{.*?\}', input_text)
    
    if match:
        json_text = match.group(0)
        try:
            # Convert the extracted text to a JSON object
            json_data = json.loads(json_text)
            return json_data
        except json.JSONDecodeError:
            return "Invalid JSON format"
    else:
        return "No JSON found in input text"

def call_gemini_with_prompt(prompt: str, input_text: str):
    """
    Calls Gemini with the provided prompt and input text.
    """
    context = f"Prompt: {prompt}\nInput: {input_text}\n\n"
    gemini_response = model.generate_content([context],  safety_settings={
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE, # type: ignore
    })

    formatted_response = extract_json_from_text(gemini_response.text )

    return(formatted_response)


@app.get("/root")
async def root():
    return {"message": "Hello World"}

@app.post("/answer")
async def generate_answer(query: Query = Body(...)):
    # Call Gemini to get the JSON response
    gemini_json_response = call_gemini_with_prompt(prompt, query.text)

    # Parse the JSON response to extract fields
    try:
        parsed_response = gemini_json_response
        medicine_name = parsed_response.get("medicine_name", "").strip()
        medicine_composition = parsed_response.get("medicine_composition", "").strip()
        disease = parsed_response.get("disease", "").strip()
    except json.JSONDecodeError:
        return {"error": "Failed to decode JSON response from Gemini."}

    # Initialize the filter for the Astra DB query
    filter_conditions = {}
    if medicine_name:
        filter_conditions["medicine_name"] = medicine_name
    if medicine_composition:
        filter_conditions["composition"] = medicine_composition
    # if disease:
    #     filter_conditions["disease"] = disease

    # Perform the Astra DB find operation with the constructed filter
    # Check if disease is present for vector search
    if disease != '':
        # Perform the Astra DB find operation with vectorization
        vector_results = my_collection.find(
            filter=filter_conditions,
            sort={"$vectorize": disease},
            limit=query.limit,
            projection={"$vectorize": True},
            include_similarity=True,
        )
    else:
        print("serching with json")
        # If no disease, find using only the other filter conditions
        vector_results = search_medicines(filter_conditions, query.limit)

    # data = [item.to_dict() for item in vector_results]
    data = vector_results
    # print(data)
    # Prepare detailed information for Gemini's second call
    medicine_details = []
    if data:
        for item in data[:5]:
            name = item.get('medicine_name', 'N/A')
            composition = item.get('composition', 'N/A')
            uses = item.get('uses', 'N/A')
            medicine_details.append(f"- Name: {name}, Composition: {composition}, Uses: {uses}")

    # Construct the context for the second Gemini call
    if medicine_details:
        medicines_info = "\n".join(medicine_details)
        context = (f"Query: {query.text}\n"
                   f"Based on the retrieved medicines:\n"
                   f"{medicines_info}\n"
                   "Please provide a comprehensive answer to inform the user about their condition, "
                   "causes, and options for relief.")
    else:
        context = f"Query: {query.text}\nNo related medicines found.\n"

    # Generate Gemini response
    gemini_response = model.generate_content(context)
    print(gemini_json_response)
    print(data)
    # print(gemini_response)

    return {
        "data": data,
        "gemini_answer": gemini_response.text
    }


prompt = """
Instructions
Understand the Input:
The query can contain:

A medicine name (e.g., "Paracetamol").
A medicine composition (e.g., "Ibuprofen").
A disease/symptom (e.g., "fever"). Extract and categorize without inferring.
Process the Query:

Medicine Name: If a known medicine name is mentioned, assign it to medicine_name.
Medicine Composition: If an active ingredient is mentioned, assign it to medicine_composition.
Disease or Symptom: If a disease or symptom is mentioned, assign it to disease.
Handle Missing Information:
If a category is not mentioned, leave it blank in the output.

Output Format:
The output will always include medicine_name, medicine_composition, and disease, filling only the provided info.

Example Queries and Outputs:
Query: "Macfast"
Output:

json
Copy code
{"medicine_name": "Macfast", "medicine_composition": "", "disease": ""}
Query: "Paracetamol for cold"
Output:

json
Copy code
{"medicine_name": "", "medicine_composition": "Paracetamol", "disease": "Cold"}
Query: "I have a fever"
Output:

json
Copy code
{"medicine_name": "", "medicine_composition": "", "disease": "Fever"}

--------------------------------

Now this is the input to query for output:

"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000 )
