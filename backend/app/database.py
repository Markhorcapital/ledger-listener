"""MongoDB database connection and operations"""
from pymongo import MongoClient
from pymongo.collection import Collection
from typing import List, Dict, Any
from urllib.parse import quote_plus
from app.config import config


class Database:
    """MongoDB database manager"""
    
    def __init__(self):
        self.client: MongoClient = None
        self.db = None
        self.collection: Collection = None
    
    def connect(self):
        """Establish MongoDB connection"""
        mongo_config = config.mongodb
        
        # URL-encode username and password to handle special characters
        username = quote_plus(mongo_config['username'])
        password = quote_plus(mongo_config['password'])
        
        connection_string = (
            f"mongodb://{username}:{password}"
            f"@{mongo_config['host']}:{mongo_config['port']}"
            f"/?authSource={mongo_config['auth_source']}"
        )
        
        self.client = MongoClient(connection_string)
        self.db = self.client[mongo_config['database']]
        self.collection = self.db[mongo_config['collection']]
    
    def disconnect(self):
        """Close MongoDB connection"""
        if self.client is not None:
            self.client.close()
    
    def get_active_accounts(self) -> List[Dict[str, Any]]:
        """
        Fetch all active CEX accounts from database
        
        Returns:
            List of account documents with credentials
        """
        if self.collection is None:
            self.connect()
        
        # Query only active accounts
        accounts = list(self.collection.find(
            {"isActive": True},
            {
                "accountId": 1,
                "exchange": 1,
                "accountName": 1,
                "apiKey": 1,
                "apiSecret": 1,
                "uid": 1,
                "_id": 0
            }
        ))
        
        return accounts


# Global database instance
db = Database()

