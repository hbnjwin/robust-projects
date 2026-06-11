from pymongo import MongoClient
from datetime import datetime, timedelta

client = MongoClient("mongodb://localhost:27017")
db = client["analytics"]

def get_user_stats(user_id: str, start_date: datetime, end_date: datetime):
    # BUG: no index on created_at, slow aggregation
    pipeline = [
        {"$match": {"user_id": user_id, "created_at": {"$gte": start_date, "$lte": end_date}}},
        {"$group": {"_id": "$category", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        {"$sort": {"total": -1}},
        # BUG: missing $limit stage, processes all data
    ]
    return list(db.transactions.aggregate(pipeline))
