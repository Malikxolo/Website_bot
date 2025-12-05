"""
MongoDB Query Agent - Business JOIN Test (From Scratch)
========================================================

Starts with EMPTY database and builds everything:
1. Create database
2. Create collections
3. Insert data
4. Test JOIN operations
5. Test complex business queries

Tests if Query Agent can handle:
- Multi-step workflows
- JOIN operations with aggregate
- Real business scenarios
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from core.mcp.mongodb import MongoDBMCPClient
from core.mcp.query_agent import QueryAgent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title):
    """Print a nice section header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")


async def run_query(query_agent, tools_prompt, instruction, mongodb_client, step_name):
    """Run a query and show results"""
    print(f"💬 {step_name}")
    print(f"   Instruction: \"{instruction}\"")
    
    result = await query_agent.execute(
        tools_prompt=tools_prompt,
        instruction=instruction,
        mcp_client=mongodb_client
    )
    
    if result.success:
        print(f"   ✅ SUCCESS")
        print(f"   Tool: {result.tool_name}")
        result_preview = str(result.result)[:200] if result.result else "No result data"
        print(f"   Result: {result_preview}...")
    else:
        print(f"   ❌ FAILED")
        print(f"   Error: {result.error}")
    
    print()
    await asyncio.sleep(0.5)
    return result


async def test_from_scratch():
    """Test JOIN operations starting from empty database"""
    
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  MONGODB JOIN TEST - STARTING FROM SCRATCH".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝\n")
    
    load_dotenv()
    
    if not os.getenv("MONGODB_MCP_CONNECTION_STRING"):
        print("❌ MONGODB_MCP_CONNECTION_STRING not set in .env")
        return
    
    # Initialize
    print("📦 Initializing MongoDB and Query Agent...")
    mongodb_client = MongoDBMCPClient()
    
    try:
        connected = await mongodb_client.connect()
        if not connected:
            print("❌ Connection failed")
            return
        print("✅ MongoDB connected\n")
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return
    
    query_agent = QueryAgent()
    tools_prompt = mongodb_client.get_tools_prompt()
    print("✅ Query Agent ready\n")
    
    DB = "join_test_db"
    
    # ========================================================================
    # PHASE 1: CREATE DATABASE & COLLECTIONS
    # ========================================================================
    print_section("PHASE 1: CREATE DATABASE & COLLECTIONS")
    
    print("📝 Note: In MongoDB, database and collections are created automatically")
    print("         when you insert the first document. Let's start inserting data!\n")
    
    # ========================================================================
    # PHASE 2: CREATE CUSTOMERS COLLECTION & DATA
    # ========================================================================
    print_section("PHASE 2: CREATE CUSTOMERS & INSERT DATA")
    
    await run_query(
        query_agent, tools_prompt,
        f"Add customer with customer_id 1, name John Doe, email john@example.com, city New York to customers collection in {DB}",
        mongodb_client,
        "Step 1: Insert customer 1 (John)"
    )
    
    await run_query(
        query_agent, tools_prompt,
        f"Add customer with customer_id 2, name Jane Smith, email jane@example.com, city Los Angeles to customers collection in {DB}",
        mongodb_client,
        "Step 2: Insert customer 2 (Jane)"
    )
    
    await run_query(
        query_agent, tools_prompt,
        f"Add customer with customer_id 3, name Bob Wilson, email bob@example.com, city Chicago to customers collection in {DB}",
        mongodb_client,
        "Step 3: Insert customer 3 (Bob)"
    )
    
    # Verify customers
    await run_query(
        query_agent, tools_prompt,
        f"Show me all documents in customers collection from {DB}",
        mongodb_client,
        "Verify: List all customers"
    )
    
    # ========================================================================
    # PHASE 3: CREATE ORDERS COLLECTION & DATA
    # ========================================================================
    print_section("PHASE 3: CREATE ORDERS & INSERT DATA")
    
    await run_query(
        query_agent, tools_prompt,
        f"Add order with order_id 101, customer_id 1, product Laptop, amount 1200 to orders collection in {DB}",
        mongodb_client,
        "Step 1: Insert order 101 (John's Laptop)"
    )
    
    await run_query(
        query_agent, tools_prompt,
        f"Add order with order_id 102, customer_id 1, product Mouse, amount 25 to orders collection in {DB}",
        mongodb_client,
        "Step 2: Insert order 102 (John's Mouse)"
    )
    
    await run_query(
        query_agent, tools_prompt,
        f"Add order with order_id 103, customer_id 2, product Keyboard, amount 75 to orders collection in {DB}",
        mongodb_client,
        "Step 3: Insert order 103 (Jane's Keyboard)"
    )
    
    await run_query(
        query_agent, tools_prompt,
        f"Add order with order_id 104, customer_id 3, product Monitor, amount 350 to orders collection in {DB}",
        mongodb_client,
        "Step 4: Insert order 104 (Bob's Monitor)"
    )
    
    await run_query(
        query_agent, tools_prompt,
        f"Add order with order_id 105, customer_id 2, product Laptop, amount 1200 to orders collection in {DB}",
        mongodb_client,
        "Step 5: Insert order 105 (Jane's Laptop)"
    )
    
    # Verify orders
    await run_query(
        query_agent, tools_prompt,
        f"Show me all documents in orders collection from {DB}",
        mongodb_client,
        "Verify: List all orders"
    )
    
    # ========================================================================
    # PHASE 4: SIMPLE QUERIES (WARM UP)
    # ========================================================================
    print_section("PHASE 4: SIMPLE QUERIES")
    
    await run_query(
        query_agent, tools_prompt,
        f"How many customers are in customers collection in {DB}",
        mongodb_client,
        "Query 1: Count customers"
    )
    
    await run_query(
        query_agent, tools_prompt,
        f"How many orders are in orders collection in {DB}",
        mongodb_client,
        "Query 2: Count orders"
    )
    
    await run_query(
        query_agent, tools_prompt,
        f"Find customer with customer_id 1 in customers collection in {DB}",
        mongodb_client,
        "Query 3: Find specific customer"
    )
    
    # ========================================================================
    # PHASE 5: JOIN OPERATIONS - THE MAIN TEST!
    # ========================================================================
    print_section("PHASE 5: JOIN OPERATIONS (THE MAIN TEST!)")
    
    print("🎯 Testing if Query Agent can do MongoDB JOIN operations")
    print("   MongoDB doesn't have SQL JOIN, but uses AGGREGATE with $lookup\n")
    
    # Test 1: Basic JOIN
    await run_query(
        query_agent, tools_prompt,
        f"""Use aggregate tool on customers collection in {DB} to join with orders collection.
        Use customer_id field to match customers with their orders.
        Show customer name and their order details.""",
        mongodb_client,
        "JOIN Test 1: Basic JOIN (customers with orders)"
    )
    
    # Test 2: JOIN with specific instructions
    await run_query(
        query_agent, tools_prompt,
        f"""In {DB}, create an aggregation pipeline on customers collection that:
        1. Uses $lookup to join with orders collection
        2. Matches on customer_id field
        3. Shows customer name, email, and all their orders""",
        mongodb_client,
        "JOIN Test 2: Explicit $lookup instruction"
    )
    
    # Test 3: Simple English JOIN request
    await run_query(
        query_agent, tools_prompt,
        f"Show me which customers placed which orders in {DB}",
        mongodb_client,
        "JOIN Test 3: Natural language JOIN"
    )
    
    # ========================================================================
    # PHASE 6: AGGREGATION OPERATIONS
    # ========================================================================
    print_section("PHASE 6: AGGREGATION OPERATIONS")
    
    await run_query(
        query_agent, tools_prompt,
        f"""Use aggregate on orders collection in {DB} to:
        Group by customer_id and calculate total amount spent by each customer""",
        mongodb_client,
        "Aggregation 1: Total spending per customer"
    )
    
    await run_query(
        query_agent, tools_prompt,
        f"""Use aggregate on orders collection in {DB} to:
        Group by product and count how many times each product was ordered""",
        mongodb_client,
        "Aggregation 2: Product popularity count"
    )
    
    # ========================================================================
    # PHASE 7: COMPLEX QUERIES
    # ========================================================================
    print_section("PHASE 7: COMPLEX QUERIES")
    
    await run_query(
        query_agent, tools_prompt,
        f"Find all orders in orders collection in {DB} where amount is greater than 100",
        mongodb_client,
        "Complex 1: Filter orders by amount"
    )
    
    await run_query(
        query_agent, tools_prompt,
        f"Find customers in customers collection in {DB} where city is Los Angeles",
        mongodb_client,
        "Complex 2: Filter customers by city"
    )
    
    await run_query(
        query_agent, tools_prompt,
        f"""In {DB}, use aggregate on customers collection to:
        1. Filter customers where city is Los Angeles
        2. Join with orders collection on customer_id
        3. Show customer name and their orders""",
        mongodb_client,
        "Complex 3: JOIN with filter (LA customers + orders)"
    )
    
    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    print("\n" + "╔" + "="*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  TEST SUMMARY".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "="*68 + "╝\n")
    
    # MongoDB stats
    stats = mongodb_client.get_stats()
    print(f"📈 MongoDB Operations:")
    print(f"   Total calls: {stats['calls']}")
    print(f"   Successful: {stats['successes']}")
    print(f"   Failed: {stats['failures']}")
    print(f"   Success rate: {stats['success_rate']:.1f}%\n")
    
    print("📊 What We Tested:")
    print("   ✅ Database & collection creation (implicit)")
    print("   ✅ Insert individual documents")
    print("   ✅ Simple queries (find, count)")
    print("   ✅ JOIN operations (aggregate + $lookup)")
    print("   ✅ Aggregation (group by, sum, count)")
    print("   ✅ Complex filters")
    print("   ✅ Multi-collection queries\n")
    
    print("💡 Key Findings:")
    print("   • Check if JOIN operations worked above")
    print("   • Look for 'aggregate' tool being used for JOINs")
    print("   • Check if $lookup syntax was generated correctly")
    print("   • Verify if results show combined data from both collections\n")
    
    print("🔍 To Verify in MongoDB Atlas:")
    print(f"   1. Go to your Atlas cluster")
    print(f"   2. Browse Collections")
    print(f"   3. Look for database: {DB}")
    print(f"   4. Check collections: customers, orders")
    print(f"   5. Verify data is there\n")
    
    # Cleanup
    await query_agent.close()
    await mongodb_client.disconnect()
    print("✅ Test completed and disconnected\n")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║       MONGODB JOIN TEST - STARTING FROM SCRATCH                  ║
║                                                                  ║
║  This test:                                                      ║
║  1. Creates fresh database                                       ║
║  2. Creates customers collection + inserts 3 customers           ║
║  3. Creates orders collection + inserts 5 orders                 ║
║  4. Tests JOIN operations (customers + orders)                   ║
║  5. Tests aggregation (group by, sum, count)                     ║
║  6. Tests complex multi-collection queries                       ║
║                                                                  ║
║  Database: join_test_db                                          ║
║  Collections: customers, orders                                  ║
║                                                                  ║
║  Data stays in MongoDB - verify in Atlas after test!             ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(test_from_scratch())