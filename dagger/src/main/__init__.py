""" 
Module Name: Financialadvisor

This module orchestrates a series of Dagger methods to provide personalized financial advice based on the user's bank transactions. By integrating various services, including spreadsheet data fetching, transaction filtering, expense categorization, MongoDB interaction, and AI-driven advice generation, this module delivers actionable insights to users via SMS.

Functions:
run_pipeline
This function runs a pipeline that processes bank transaction data to generate financial advice using AI, then sends this advice to the user via SMS.

Args:

apiKey (Secret): A Secret object storing the API key for accessing the spreadsheet containing transaction data.
sheet (Secret): A Secret object storing the identifier of the spreadsheet to be accessed.
connection (Secret): A Secret object storing the MongoDB connection string for database access.
hftoken (Secret): A Secret object storing the Hugging Face API token for categorizing expenses.
openai (Secret): A Secret object storing the OpenAI API key for generating financial advice.
textBelt (Secret): A Secret object storing the TextBelt API key for sending SMS messages.
mobileNums (str): A comma-separated string of mobile numbers to send the financial advice to.
database (str): The name of the MongoDB database to interact with.
collection (str): The name of the MongoDB collection to interact with.

Returns:

A string indicating the success or failure of the SMS sending process.

Example Use Case:

dagger call run_pipeline --apiKey=env:API_KEY --sheet=env:SHEET_ID --connection=env:DB_CONNECTION --hftoken=env:HF_TOKEN --openai=env:OPENAI_SECRET --textBelt=env:TEXTBELT_KEY --mobileNums='+1234567890,+0987654321' --database='financial_data' --collection='transactions'

This command fetches the latest transaction data, filters for new transactions, categorizes expenses, writes categorized transactions to MongoDB, retrieves data for advice generation, generates advice using AI, and sends the advice via SMS.

Function - send:
This function sends the generated financial advice as an SMS to multiple recipients using the TextBelt service.

Args:

encoded_message (str): The URL-encoded financial advice message to be sent.
mobile (str): A comma-separated string of mobile numbers to send the message to.
textBelt (Secret): A Secret object storing the TextBelt API key for sending SMS messages.

Returns:

A string indicating the result of the SMS sending process.

Example Use Case:

dagger call send --encoded_message='Your%20financial%20advice%20here' --mobile='+1234567890,+0987654321' --textBelt=env:TEXTBELT_KEY

This command sends the provided financial advice to the specified mobile numbers using the TextBelt API.

Technical Details
The `run_pipeline` function follows a multi-step process:

1. **Fetch Spreadsheet Data**: Retrieves bank transaction data from a specified spreadsheet.
2. **Filter for New Transactions**: Identifies new transactions that haven't been processed before.
3. **Categorize Expenses**: Uses a zero-shot model to categorize the new transactions by spend.
4. **Write to MongoDB**: Stores the categorized transactions in a MongoDB collection.
5. **Retrieve Data for Advice Generation**: Fetches data from MongoDB to be used for generating financial advice.
6. **Generate Financial Advice**: Utilizes OpenAI's GPT models to generate personalized financial advice based on the retrieved data.
7. **Send Advice via SMS**: Sends the generated advice to the user's mobile numbers using the TextBelt service.

The `send` function iterates through the list of provided mobile numbers and uses a CURL command within a Docker container to send the SMS messages.

This module aims to streamline the process of obtaining and delivering AI-driven financial advice, making it a valuable tool for personal finance management and advisory services.
"""

from dagger import dag, function, object_type, Secret
import urllib.parse
import json
import asyncio
import os

@object_type
class Financialadvisor:
    @function
    async def run_pipeline(self, apiKey: Secret, sheet: Secret, connection: Secret, hftoken: Secret, openai: Secret, textBelt: Secret, database: str, collection: str) -> str:
        """Returns a container that echoes whatever string argument is provided"""
        json_resp = await dag.fetch_spreadsheet_data().fetch_data(apiKey, sheet)
        new_transactions = await dag.filter_for_new_transactions().filter(json_resp, connection, database, collection)
        categorized_transactions = await dag.categorize_expenses().categorize(new_transactions, hftoken)
        write_to_mongo = await dag.write_to_mongo().write(categorized_transactions, connection, database, collection)
        get_data = await dag.get_from_mongo().get_data(connection, database, collection)
        generate_resp = await dag.get_advice().generate(get_data, openai, connection)
        resp_dict = json.loads(generate_resp).get('advice')
        encoded_message = urllib.parse.quote(resp_dict)
        return await self.send(encoded_message, textBelt)
    @function
    async def send(self, encoded_message: str, textBelt: Secret) -> str:
        """Returns lines that match a pattern in the files of the provided Directory"""
        phone_numbers = ['15162341744', '15512259418']
        text_belt_key = await textBelt.plaintext()
        for phone_number in phone_numbers:
            curl_cmd = f"curl -X POST https://textbelt.com/text --data-urlencode phone='{phone_number}' --data-urlencode message='{encoded_message}' -d key='{text_belt_key}'"
            try:
                result = await (
                    dag.container()
                    .from_("curlimages/curl:latest")
                    .with_exec(["sh", "-c", curl_cmd])
                    .stdout()
                )
                if "success" not in result:
                    raise ValueError(f"Failed to send message to {phone_number}: {result}")
            except Exception as e:
                raise RuntimeError(f"Error sending message to {phone_number}: {e}")
        return result
    
if __name__ == "__main__":

    advisor = Financialadvisor()
    asyncio.run(advisor.run_pipeline(
        apiKey=Secret(os.getenv('API_KEY')),
        sheet=Secret(os.getenv('SHEET_ID')),
        connection=Secret(os.getenv('DB_CONNECTION')),
        hftoken=Secret(os.getenv('HF_TOKEN')),
        openai=Secret(os.getenv('OPENAI_KEY')),
        textBelt=Secret(os.getenv('TEXTBELT_KEY')),
        database=os.getenv('DATABASE'),
        collection=os.getenv('COLLECTION')
    ))
