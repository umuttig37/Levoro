"""
Database Backup Script

Creates a JSON backup of all collections in the current database.
Backup is stored in backups/ directory with timestamp.
"""

import sys
import os
from pathlib import Path
import json
from datetime import datetime

# Add parent directory to path so we can import models
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.database import db_manager


def backup_database():
    """Backup all collections to JSON files"""
    
    # Get database instance
    db = db_manager.db
    
    # Get database name
    db_name = db.name
    print(f"[BACKUP] Database: {db_name}")
    print("=" * 60)
    
    # Create backup directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(__file__).parent.parent / "backups" / f"{db_name}_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[BACKUP] Directory: {backup_dir}")
    print()
    
    # Get all collection names
    collection_names = db.list_collection_names()
    print(f"[BACKUP] Found {len(collection_names)} collections")
    print()
    
    total_docs = 0
    
    # Backup each collection
    for collection_name in collection_names:
        collection = db[collection_name]
        documents = list(collection.find({}))
        doc_count = len(documents)
        total_docs += doc_count
        
        # Convert ObjectId and datetime to strings for JSON serialization
        def serialize_doc(obj):
            """Recursively serialize MongoDB documents"""
            if hasattr(obj, 'isoformat'):  # datetime objects
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: serialize_doc(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize_doc(item) for item in obj]
            elif hasattr(obj, '__str__') and type(obj).__name__ == 'ObjectId':
                return str(obj)
            else:
                return obj
        
        serialized_documents = [serialize_doc(doc) for doc in documents]
        
        # Save to JSON file
        backup_file = backup_dir / f"{collection_name}.json"
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(serialized_documents, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ {collection_name}: {doc_count} documents")
    
    # Create metadata file
    metadata = {
        'database': db_name,
        'timestamp': timestamp,
        'backup_date': datetime.now().isoformat(),
        'collections': collection_names,
        'total_documents': total_docs
    }
    
    metadata_file = backup_dir / "_metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    print()
    print("=" * 60)
    print(f"[BACKUP COMPLETE]")
    print(f"  - Total documents: {total_docs}")
    print(f"  - Location: {backup_dir}")
    print("=" * 60)
    
    return backup_dir


if __name__ == "__main__":
    print("=" * 60)
    print("MongoDB Database Backup")
    print("=" * 60)
    print()
    
    try:
        backup_dir = backup_database()
        print(f"\n✓ Backup successful!")
        print(f"\nYou can now safely run migrations.")
    except Exception as e:
        print(f"\n✗ Backup failed: {str(e)}")
        sys.exit(1)
