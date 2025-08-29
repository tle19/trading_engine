class AccountsTrading:
    def __init__(self):
        # Initialize access token during class instantiation
        self.access_token = None
        self.account_hash_value = None
        self.refresh_access_token()
        self.base_url = "https://api.schwabapi.com/trader/v1"
        self.headers = {"Authorization": f"Bearer {self.access_token}"}
        self.get_account_number_hash_value()

    def refresh_access_token(self):
        # Custom function to retrieve access token from Firestore
        self.access_token = retrieve_firestore_value(
            collection_id="your-collection-id",
            document_id="your-doc-id",
            key="your-access-token",
        )

    def get_account_number_hash_value(self):
        response = requests.get(
            self.base_url + f"/accounts/accountNumbers", headers=self.headers
        )
        response_frame = pandas.json_normalize(response.json())
        self.account_hash_value = response_frame["hashValue"].iloc[0]