from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import models, crud, schemas
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)  # create tables
app = FastAPI()

# Enable CORS for local/remote frontend flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SmartCatalog - Semantic Search & RAG Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Plus+Jakarta+Sans:wght@300;400;500;700&display=swap" rel="stylesheet">
        <style>
            body {
                font-family: 'Plus Jakarta Sans', sans-serif;
                background: radial-gradient(circle at 50% 50%, #111827 0%, #030712 100%);
            }
            .font-outfit { font-family: 'Outfit', sans-serif; }
            .glass {
                background: rgba(17, 24, 39, 0.7);
                backdrop-filter: blur(12px);
                border: 1px rgba(255, 255, 255, 0.08) solid;
            }
            .glow-btn:hover {
                box-shadow: 0 0 15px rgba(99, 102, 241, 0.4);
            }
        </style>
    </head>
    <body class="text-gray-100 min-h-screen pb-12">
        <header class="border-b border-gray-800 bg-gray-900/50 backdrop-blur-md sticky top-0 z-50">
            <div class="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
                <div class="flex items-center space-x-3">
                    <div class="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
                        <span class="text-white font-bold text-xl font-outfit">S</span>
                    </div>
                    <div>
                        <h1 class="text-xl font-bold font-outfit bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-purple-400">SmartCatalog</h1>
                        <p class="text-xs text-gray-400">SQL + Vector Hybrid Demo</p>
                    </div>
                </div>
                <button onclick="seedDatabase()" class="px-4 py-2 bg-indigo-600/20 border border-indigo-500/30 hover:bg-indigo-600/40 text-indigo-300 font-medium rounded-lg text-sm transition duration-300 glow-btn">
                    🌱 Seed Catalog Data
                </button>
            </div>
        </header>

        <main class="max-w-7xl mx-auto px-4 mt-8 grid grid-cols-1 lg:grid-cols-12 gap-8">
            <!-- Left Side: Catalog Controls & Add Form (5 cols) -->
            <div class="lg:col-span-5 space-y-6">
                <!-- Add Product -->
                <div class="glass p-6 rounded-2xl">
                    <h2 class="text-lg font-semibold font-outfit text-indigo-400 mb-4">➕ Add New Product</h2>
                    <form id="add-product-form" class="space-y-4" onsubmit="addProduct(event)">
                        <div>
                            <label class="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Product Name</label>
                            <input id="prod-name" type="text" required class="w-full bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition">
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Price (INR)</label>
                                <input id="prod-price" type="number" required class="w-full bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition">
                            </div>
                            <div>
                                <label class="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Active Status</label>
                                <select id="prod-active" class="w-full bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition">
                                    <option value="true">Active</option>
                                    <option value="false">Inactive</option>
                                </select>
                            </div>
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Description</label>
                            <textarea id="prod-desc" required rows="3" class="w-full bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition"></textarea>
                        </div>
                        <button type="submit" class="w-full py-2 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white font-semibold rounded-lg text-sm shadow-md transition duration-300 transform active:scale-95">
                            Add Product & Sync to VectorDB
                        </button>
                    </form>
                </div>

                <!-- Active Catalog -->
                <div class="glass p-6 rounded-2xl">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-lg font-semibold font-outfit text-indigo-400">📦 Live Catalog</h2>
                        <button onclick="loadCatalog()" class="text-xs text-gray-400 hover:text-indigo-400">🔄 Refresh</button>
                    </div>
                    <div id="catalog-list" class="space-y-3 max-h-[300px] overflow-y-auto pr-2">
                        <p class="text-xs text-gray-400 italic">No products listed. Click 'Seed Catalog Data' above!</p>
                    </div>
                </div>
            </div>

            <!-- Right Side: Search & recommendation Playground (7 cols) -->
            <div class="lg:col-span-7 space-y-6">
                <!-- Search panel -->
                <div class="glass p-6 rounded-2xl">
                    <h2 class="text-lg font-semibold font-outfit text-indigo-400 mb-4">🔍 Search & Filter Engine</h2>
                    <div class="space-y-4">
                        <div>
                            <label class="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Query String</label>
                            <input id="search-query" type="text" placeholder="e.g., calling device, running shoes, headphones" class="w-full bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-indigo-500 transition">
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Max Price Limit (INR)</label>
                                <input id="search-price" type="number" placeholder="No limit" class="w-full bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition">
                            </div>
                            <div>
                                <label class="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Active Status Only</label>
                                <select id="search-active" class="w-full bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 transition">
                                    <option value="">All items</option>
                                    <option value="true">Active only</option>
                                    <option value="false">Inactive only</option>
                                </select>
                            </div>
                        </div>
                        <div class="grid grid-cols-3 gap-4 pt-2">
                            <button onclick="runSearch('keyword')" class="py-2.5 bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 rounded-lg font-medium text-xs transition">
                                📝 Keyword SQL
                            </button>
                            <button onclick="runSearch('semantic')" class="py-2.5 bg-indigo-950 hover:bg-indigo-900 text-indigo-300 border border-indigo-800 rounded-lg font-medium text-xs transition">
                                🌌 Semantic Vector
                            </button>
                            <button onclick="runRecommend()" class="py-2.5 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white rounded-lg font-semibold text-xs shadow-md transition">
                                🤖 Get RAG Advice
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Results & prompt details panel -->
                <div id="results-panel" class="hidden glass p-6 rounded-2xl transition duration-500">
                    <div class="flex justify-between items-center mb-4 border-b border-gray-800 pb-3">
                        <h3 id="results-title" class="font-semibold text-md font-outfit text-indigo-400">Results</h3>
                        <span id="results-badge" class="px-2 py-0.5 text-[10px] uppercase font-bold rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800"></span>
                    </div>

                    <!-- Retrieved Database candidates -->
                    <div class="mb-6">
                        <h4 class="text-xs uppercase tracking-wider text-gray-400 font-bold mb-3">📍 Database Retrievals (Grounding Context)</h4>
                        <div id="retrievals-list" class="space-y-3"></div>
                    </div>

                    <!-- Prompt & Recommendation Details (Visible on /recommend) -->
                    <div id="rag-details" class="hidden space-y-4">
                        <div>
                            <h4 class="text-xs uppercase tracking-wider text-gray-400 font-bold mb-2">📜 Prompt Sent to LLM</h4>
                            <pre id="prompt-box" class="w-full bg-gray-950 border border-gray-950 p-4 rounded-xl text-[11px] text-gray-300 font-mono overflow-x-auto max-h-[250px] whitespace-pre-wrap"></pre>
                        </div>
                        <div>
                            <h4 class="text-xs uppercase tracking-wider text-gray-400 font-bold mb-2">✨ Generated recommendation</h4>
                            <div id="recommendation-box" class="w-full bg-indigo-950/30 border border-indigo-900/50 p-4 rounded-xl text-sm text-gray-200 leading-relaxed whitespace-pre-wrap"></div>
                        </div>
                    </div>
                </div>
            </div>
        </main>

        <script>
            const host = "";

            async function loadCatalog() {
                try {
                    const res = await fetch(`${host}/items/`);
                    const data = await res.json();
                    const list = document.getElementById("catalog-list");
                    list.innerHTML = "";
                    if (data.length === 0) {
                        list.innerHTML = `<p class="text-xs text-gray-400 italic">No products listed. Click 'Seed Catalog' above!</p>`;
                        return;
                    }
                    data.forEach(item => {
                        list.innerHTML += `
                            <div class="flex justify-between items-center p-3 bg-gray-900/40 border border-gray-800/80 rounded-xl hover:border-gray-700 transition">
                                <div>
                                    <h4 class="font-bold text-xs">${item.name}</h4>
                                    <p class="text-[10px] text-gray-400 max-w-[280px] truncate">${item.description || ''}</p>
                                </div>
                                <div class="text-right">
                                    <span class="text-xs font-bold text-indigo-400">₹${item.price}</span>
                                    <span class="block text-[8px] text-gray-500 uppercase font-bold">${item.is_active ? 'Active' : 'Inactive'}</span>
                                </div>
                            </div>
                        `;
                    });
                } catch(e) {
                    console.error("Failed to load catalog:", e);
                }
            }

            async function addProduct(e) {
                e.preventDefault();
                const name = document.getElementById("prod-name").value;
                const price = parseInt(document.getElementById("prod-price").value);
                const is_active = document.getElementById("prod-active").value === "true";
                const description = document.getElementById("prod-desc").value;

                try {
                    const res = await fetch(`${host}/items/`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({name, price, is_active, description})
                    });
                    if (res.ok) {
                        document.getElementById("add-product-form").reset();
                        loadCatalog();
                        alert("Product created and synced successfully!");
                    } else {
                        alert("Failed to create product.");
                    }
                } catch(err) {
                    console.error("Error creating product:", err);
                }
            }

            async function seedDatabase() {
                if (!confirm("Are you sure you want to purge and seed the database?")) return;
                try {
                    const res = await fetch(`${host}/items/seed`, {method: 'POST'});
                    if (res.ok) {
                        loadCatalog();
                        alert("Database seeded successfully!");
                    }
                } catch(e) {
                    alert("Error seeding database.");
                }
            }

            async function runSearch(mode) {
                const query = document.getElementById("search-query").value;
                if (!query) { alert("Please input a query first!"); return; }

                const maxPrice = document.getElementById("search-price").value;
                const isActive = document.getElementById("search-active").value;

                let url = `${host}/items/search/${mode}?query=${encodeURIComponent(query)}`;
                if (maxPrice) url += `&max_price=${maxPrice}`;
                if (isActive) url += `&is_active=${isActive}`;

                try {
                    const res = await fetch(url);
                    const items = await res.json();
                    
                    document.getElementById("results-panel").classList.remove("hidden");
                    document.getElementById("rag-details").classList.add("hidden");
                    document.getElementById("results-title").innerText = `${mode.toUpperCase()} Search Results`;
                    document.getElementById("results-badge").innerText = `${items.length} Match(es)`;

                    renderRetrievals(items);
                } catch(e) {
                    console.error(e);
                }
            }

            async function runRecommend() {
                const query = document.getElementById("search-query").value;
                if (!query) { alert("Please input a query first!"); return; }

                const maxPrice = document.getElementById("search-price").value;
                const isActive = document.getElementById("search-active").value;

                let url = `${host}/items/recommend?query=${encodeURIComponent(query)}`;
                if (maxPrice) url += `&max_price=${maxPrice}`;
                if (isActive) url += `&is_active=${isActive}`;

                try {
                    const res = await fetch(url);
                    const data = await res.json();
                    
                    document.getElementById("results-panel").classList.remove("hidden");
                    document.getElementById("rag-details").classList.remove("hidden");
                    document.getElementById("results-title").innerText = `RAG recommendation`;
                    document.getElementById("results-badge").innerText = `Gemini Response`;

                    renderRetrievals(data.retrieved_items);
                    document.getElementById("prompt-box").innerText = data.prompt_sent;
                    document.getElementById("recommendation-box").innerText = data.recommendation;
                } catch(e) {
                    console.error(e);
                }
            }

            function renderRetrievals(items) {
                const list = document.getElementById("retrievals-list");
                list.innerHTML = "";
                if (items.length === 0) {
                    list.innerHTML = `<p class="text-xs text-gray-400 italic">No products matched this criteria.</p>`;
                    return;
                }
                items.forEach(item => {
                    list.innerHTML += `
                        <div class="p-3 bg-gray-900 border border-gray-800 rounded-xl">
                            <div class="flex justify-between items-center mb-1">
                                <h5 class="font-semibold text-xs text-indigo-300">${item.name}</h5>
                                <span class="text-xs font-bold text-indigo-400">₹${item.price}</span>
                            </div>
                            <p class="text-[11px] text-gray-400">${item.description}</p>
                        </div>
                    `;
                });
            }

            // Init load
            window.onload = loadCatalog;
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

# Depends(get_db) injects a live DB session per request
@app.post("/items/", response_model=schemas.ItemResponse, status_code=201)
def create_item(item: schemas.ItemCreate,
    db: Session = Depends(get_db)):
    return crud.create_item(db=db, item=item)

@app.get("/items/", response_model=list[schemas.ItemResponse])
def read_items(skip=0, limit=100, db = Depends(get_db)):
    return crud.get_items(db=db, skip=skip, limit=limit)

@app.post("/items/seed", response_model=list[schemas.ItemResponse])
def seed_database(db: Session = Depends(get_db)):
    return crud.seed_db(db=db)

@app.get("/items/search/keyword", response_model=list[schemas.ItemResponse])
def search_keyword(query: str, max_price: int = None, is_active: bool = None, db: Session = Depends(get_db)):
    return crud.search_items_keyword(db=db, query=query, max_price=max_price, is_active=is_active)

@app.get("/items/search/semantic", response_model=list[schemas.ItemResponse])
def search_semantic(query: str, limit: int = 5, max_price: int = None, is_active: bool = None):
    return crud.search_items_semantic(query=query, limit=limit, max_price=max_price, is_active=is_active)

@app.get("/items/recommend", response_model=schemas.RecommendationResponse)
def get_recommendation(query: str, limit: int = 3, max_price: int = None, is_active: bool = None):
    # Retrieve candidates using semantic search
    items = crud.search_items_semantic(query=query, limit=limit, max_price=max_price, is_active=is_active)
    # Generate RAG recommendation
    return crud.generate_recommendation(query=query, items=items)

@app.get("/items/{item_id}", response_model=schemas.ItemResponse)
def read_item(item_id: int, db = Depends(get_db)):
    item = crud.get_item(db=db, item_id=item_id)
    if not item: raise HTTPException(407, "Not found")
    return item

@app.put("/items/{item_id}", response_model=schemas.ItemResponse)
def update_item(item_id: int, updates: schemas.ItemUpdate,
    db = Depends(get_db)):
    item = crud.update_item(db=db, item_id=item_id, updates=updates)
    if not item: raise HTTPException(404, "Not found")
    return item

@app.delete("/items/{item_id}", response_model=schemas.ItemResponse)
def delete_item(item_id: int, db = Depends(get_db)):
    item = crud.delete_item(db=db, item_id=item_id)
    if not item: raise HTTPException(404, "Not found")
    return item


