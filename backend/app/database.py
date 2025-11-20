"""MongoDB database connection and operations"""
from pymongo import MongoClient
from pymongo.collection import Collection
from typing import List, Dict, Any
from urllib.parse import quote_plus
from app.config import config
from app.encryption import Encryption
import logging

logger = logging.getLogger(__name__)


class Database:
    """MongoDB database manager"""
    
    def __init__(self):
        self.client: MongoClient = None
        self.db = None
        self.collection: Collection = None
        # Initialize encryption with secret from config
        encryption_secret = config.get('encryption.secret')
        self.encryption = Encryption(encryption_secret) if encryption_secret else None
    
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
        Fetch all CEX accounts from database and decrypt API credentials
        
        Returns:
            List of account documents with decrypted credentials
        """
        if self.collection is None:
            self.connect()
        
        # Query all documents from apicredentials collection
        accounts = list(self.collection.find(
            {},
            {
                "name": 1,
                "exchange": 1,
                "accountName": 1,
                "apiKey": 1,
                "apiSecret": 1,
                "_id": 0
            }
        ))
        
        # Transform and decrypt
        result = []
        for account in accounts:
            # Map exchange names to match config.yml format
            exchange_raw = account.get('exchange', '').lower()
            exchange_map = {
                'gate': 'Gate_io',
                'gate.io': 'Gate_io',
                'gateio': 'Gate_io',
                'htx': 'HTX',
                'mexc': 'MEXC',
                'crypto': 'Crypto_com',
                'crypto.com': 'Crypto_com',
                'cryptocom': 'Crypto_com',
                'crypto_com': 'Crypto_com'  # Added explicit mapping
            }
            exchange_name = exchange_map.get(exchange_raw, exchange_raw.upper())
            
            # Create accountId from components
            account_name = account.get('accountName', '')
            account_id = f"{account.get('name', 'unknown')}-{exchange_raw}-{account_name}".lower()
            
            transformed = {
                'accountId': account_id,
                'exchange': exchange_name,
                'accountName': account_name,
                'apiKey': account.get('apiKey', ''),
                'apiSecret': account.get('apiSecret', ''),
            }
            
            # Decrypt both apiKey and apiSecret if encryption is enabled
            if self.encryption:
                for field in ['apiKey', 'apiSecret']:
                    if transformed[field] and ':' in transformed[field]:
                        try:
                            transformed[field] = self.encryption.decrypt(transformed[field])
                            logger.debug(f"Decrypted {field} for {account_name}")
                        except Exception as e:
                            logger.error(f"Failed to decrypt {field} for {account_name}: {str(e)}")
                            # Keep encrypted value if decryption fails
            
            result.append(transformed)
        
        logger.info(f"Loaded {len(result)} accounts from database")
        return result


# Global database instance
db = Database()

