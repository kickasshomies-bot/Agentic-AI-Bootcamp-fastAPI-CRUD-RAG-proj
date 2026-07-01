from sqlalchemy.orm import Session
import models, schemas
import chromadb
import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env using absolute path
load_dotenv(dotenv_path="c:/class_proj/temp_start/.env")

# Attempt to configure Gemini if key is available
api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    has_gemini = True
else:
    has_gemini = False


# Initialize ChromaDB persistent client
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="products")

def sync_to_chroma(db_item):
    """Helper to upsert an item into ChromaDB."""
    collection.upsert(
        ids=[str(db_item.id)],
        documents=[db_item.description or ""],
        metadatas=[{
            "id": db_item.id,
            "name": db_item.name,
            "price": db_item.price,
            "is_active": db_item.is_active,
            "description": db_item.description or ""
        }]
    )

def create_item(db: Session, item: schemas.ItemCreate):
    db_item = models.Item(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)  # get the assigned id back
    
    # Sync to ChromaDB
    sync_to_chroma(db_item)
    return db_item

def get_items(db, skip=0, limit=100):
    return db.query(models.Item).offset(skip).limit(limit).all()

def get_item(db, item_id):
    return db.query(models.Item).filter(
        models.Item.id == item_id).first()

def update_item(db, item_id, updates):
    db_item = get_item(db, item_id)
    if not db_item: return None
    for f, v in updates.model_dump(exclude_unset=True).items():
        setattr(db_item, f, v)  # only update sent fields
    db.commit()
    db.refresh(db_item)
    
    # Sync update to ChromaDB
    sync_to_chroma(db_item)
    return db_item

def delete_item(db, item_id):
    db_item = get_item(db, item_id)
    if not db_item: return None
    db.delete(db_item)
    db.commit()
    
    # Delete from ChromaDB
    collection.delete(ids=[str(item_id)])
    return db_item

def seed_db(db: Session):
    """Seed the database with sample products for search demonstrations."""
    # 1. Clear existing items from SQL and ChromaDB
    db.query(models.Item).delete()
    db.commit()
    
    global collection
    try:
        chroma_client.delete_collection(name="products")
    except Exception:
        pass
    collection = chroma_client.get_or_create_collection(name="products")
    
    # 2. Seed items
    seed_data = [
        {
            "name": "iPhone 15 Pro",
            "price": 120000,
            "description": "Flagship mobile phone with 5G connectivity, 120Hz OLED screen, and advanced triple-camera system.",
            "is_active": True
        },
        {
            "name": "Samsung Galaxy A14",
            "price": 15000,
            "description": "Budget-friendly cellular smartphone with long-lasting battery and dual SIM support.",
            "is_active": True
        },
        {
            "name": "MacBook Pro M3",
            "price": 170000,
            "description": "High-performance ultrabook laptop for software developers, featuring 32GB RAM and 1TB SSD.",
            "is_active": True
        },
        {
            "name": "Sony WH-1000XM5",
            "price": 30000,
            "description": "Over-ear wireless bluetooth headphones with active noise cancellation and high-fidelity sound.",
            "is_active": True
        },
        {
            "name": "Nike Air Zoom Running Shoes",
            "price": 8000,
            "description": "Comfortable running shoes designed for marathon runners with breathable mesh fabric.",
            "is_active": True
        },
        {
            "name": "Leather Wallet",
            "price": 1500,
            "description": "Genuine leather bi-fold wallet for men with RFID blocking card slots.",
            "is_active": True
        },
        {
            "name": "iPad Air",
            "price": 60000,
            "description": "Slim and powerful tablet with a liquid retina display, support for Apple Pencil, and cellular capabilities.",
            "is_active": True
        }
    ]
    
    seeded_items = []
    for item_dict in seed_data:
        item_schema = schemas.ItemCreate(**item_dict)
        db_item = create_item(db, item_schema)
        seeded_items.append(db_item)
        
    return seeded_items

def search_items_keyword(db: Session, query: str, max_price: int = None, is_active: bool = None):
    """Case-insensitive keyword search matching the description field in SQLite with filters."""
    q = db.query(models.Item).filter(
        models.Item.description.ilike(f"%{query}%")
    )
    if max_price is not None:
        q = q.filter(models.Item.price <= max_price)
    if is_active is not None:
        q = q.filter(models.Item.is_active == is_active)
    return q.all()

#case sensitive :abc Mobile xyz, mobile MoBiLe

def search_items_semantic(query: str, limit: int = 5, max_price: int = None, is_active: bool = None):
    """Semantic vector search matching the description in ChromaDB with metadata filters."""
    where_conditions = []
    if max_price is not None:
        where_conditions.append({"price": {"$lte": max_price}})
    if is_active is not None:
        where_conditions.append({"is_active": {"$eq": is_active}})
        
    where = None
    if len(where_conditions) == 1:
        where = where_conditions[0]
    elif len(where_conditions) > 1:
        where = {"$and": where_conditions}

    results = collection.query(
        query_texts=[query],
        n_results=limit,
        where=where
    )
    
    items = []
    if results and results.get('metadatas'):
        for metadata_list in results['metadatas']:
            for meta in metadata_list:
                items.append({
                    "id": meta["id"],
                    "name": meta["name"],
                    "price": meta["price"],
                    "is_active": meta["is_active"],
                    "description": meta.get("description")
                })
    return items

def generate_recommendation(query: str, items: list[dict]):
    """Constructs a RAG prompt and retrieves a product recommendation via Gemini."""
    # 1. Format the items context
    context_parts = []
    for i, item in enumerate(items, start=1):
        context_parts.append(
            f"{i}. Product Name: {item['name']}\n"
            f"   Price: INR {item['price']}\n"
            f"   Description: {item['description']}\n"
        )
    context_str = "\n".join(context_parts) if context_parts else "No matching products found in the catalog."

    # 2. Build the prompt
    system_instruction = (
        "You are a helpful product assistant for an e-commerce platform. "
        "Your job is to recommend the best products from the provided catalog context based on the user's request. "
        "Always reference the products by name, justify your selection based on their descriptions, and be concise."
    )
    
    user_prompt = (
        f"User Request: \"{query}\"\n\n"
        f"Available Product Catalog Context:\n"
        f"-----------------------------------\n"
        f"{context_str}\n"
        f"-----------------------------------\n\n"
        f"Please provide a friendly, tailored recommendation based on the catalog above."
    )

    full_prompt = f"System Instruction:\n{system_instruction}\n\nUser Prompt:\n{user_prompt}"

    # Reload dotenv dynamically in case of recent edits, and evaluate key
    load_dotenv(dotenv_path="c:/class_proj/temp_start/.env")
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    has_live_gemini = False

    if api_key:
        genai.configure(api_key=api_key)
        has_live_gemini = True

    # 3. Call LLM or Simulate
    if has_live_gemini:
        try:
            # Use 'gemini-2.5-flash' which is supported by this API key and environment
            model = genai.GenerativeModel(model_name='gemini-2.5-flash')
            response = model.generate_content(f"{system_instruction}\n\n{user_prompt}")
            recommendation_text = response.text
        except Exception as e:
            recommendation_text = f"[Gemini Error: {str(e)}]\n\n[Fallback Mock Recommendation]: Based on your request for '{query}', I recommend the: " + (items[0]['name'] if items else "No items available")
    else:
        # Prompt Simulator Fallback
        recommendation_text = (
            "[Simulated LLM Recommendation - Set GEMINI_API_KEY env var for live results]\n\n"
            f"Based on your query: \"{query}\", I analyzed the catalog and recommend the following product:\n\n"
        )
        if items:
            best_match = items[0]
            recommendation_text += (
                f"**{best_match['name']}** (INR {best_match['price']})\n"
                f"Description: {best_match['description']}\n\n"
                f"Why: This product matches your request most closely based on its semantic similarity score in ChromaDB. "
                "If we had a live Gemini connection, it would write a custom personalized response matching these specs!"
            )
        else:
            recommendation_text += "We couldn't find any products in our catalog matching your price or search criteria."

    return {
        "query": query,
        "retrieved_items": items,
        "prompt_sent": full_prompt,
        "recommendation": recommendation_text
    }



