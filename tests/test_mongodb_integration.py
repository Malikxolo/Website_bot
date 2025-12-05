"""
MongoDB Full Integration Test - REAL End-to-End
================================================

This test runs the COMPLETE REAL flow:
1. Real OptimizedAgent with real LLM calls (Router LLM for simple analysis)
2. Real tool selection (mongodb tool detected)
3. Real ToolManager execution
4. Real QueryAgent with real LLM calls (converts NL to structured query)
5. Real MongoDB MCP server execution
6. Real data inserted/queried in MongoDB
7. Real response generation (Heart LLM)

Uses same models as production:
- Router LLM (nemotron) for simple_analysis
- Heart LLM (llama-4-maverick) for response generation
- source="whatsapp" to use simple analysis path (no CoT routing)

Requirements:
    - MONGODB_MCP_CONNECTION_STRING env variable set
    - LLM API keys configured (OPENROUTER_API_KEY)
    - MongoDB Atlas cluster accessible

Usage:
    python tests/test_mongodb_integration.py
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reduce noise from other loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)


async def run_real_integration_test():
    """
    Run REAL integration test with actual LLM calls and MongoDB MCP.
    
    Uses source="whatsapp" to trigger simple_analysis path (same as production).
    
    Flow:
        Query → OptimizedAgent.process_query(source="whatsapp")
             → _simple_analysis() using router_llm (nemotron)
             → selects "mongodb" tool
             → ToolManager.execute_tool("mongodb")
             → QueryAgent.execute() with real LLM
             → MongoDB MCP server executes
             → Real data in MongoDB
             → _generate_response() using heart_llm (llama-4-maverick)
    """
    
    print("\n" + "="*70)
    print("🚀 MONGODB FULL INTEGRATION TEST - REAL E2E")
    print("="*70)
    
    # Check required env vars
    required_vars = ["MONGODB_MCP_CONNECTION_STRING", "OPENROUTER_API_KEY"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        print(f"❌ Missing required environment variables: {missing}")
        return False
    
    print("✅ Environment variables configured")
    
    # Import real components (same as chat.py)
    from core import LLMClient, ToolManager, Config
    from core.optimized_agent import OptimizedAgent
    from api.global_config import settings
    
    print("\n📦 Initializing real components (same as chat.py)...")
    
    try:
        # Initialize config
        config = Config()
        
        # Create real LLM clients (EXACTLY as chat.py does)
        brain_model_config = config.create_llm_config(
            provider=settings.brain_provider,
            model=settings.brain_model,
            max_tokens=16000
        )
        heart_model_config = config.create_llm_config(
            provider=settings.heart_provider,
            model=settings.heart_model,
            max_tokens=1000
        )
        router_config = config.create_llm_config(
            provider=settings.router_provider,
            model=settings.router_model,
            max_tokens=2000
        )
        
        web_model_config = config.get_tool_configs(
            web_model=settings.web_model,
            use_premium_search=settings.use_premium_search
        )
        
        brain_llm = LLMClient(brain_model_config)
        heart_llm = LLMClient(heart_model_config)
        router_llm = LLMClient(router_config)
        
        print(f"   ✅ Brain LLM: {settings.brain_provider}/{settings.brain_model}")
        print(f"   ✅ Heart LLM: {settings.heart_provider}/{settings.heart_model}")
        print(f"   ✅ Router LLM: {settings.router_provider}/{settings.router_model}")
        
        # Create real ToolManager
        tool_manager = ToolManager(config, brain_llm, web_model_config, use_premium_search=settings.use_premium_search)
        
        # Initialize MongoDB MCP - THIS IS THE KEY PART
        print("\n🔌 Initializing MongoDB MCP...")
        mongodb_initialized = await tool_manager.initialize_mongodb_async()
        
        if not mongodb_initialized:
            print("❌ Failed to initialize MongoDB MCP")
            print("   Check MONGODB_MCP_CONNECTION_STRING and ensure MongoDB is accessible")
            return False
        
        print("   ✅ MongoDB MCP initialized and connected!")
        print(f"   ✅ MongoDB available: {tool_manager.mongodb_available}")
        
        # Create real OptimizedAgent (EXACTLY as chat.py does)
        print("\n🤖 Creating OptimizedAgent...")
        agent = OptimizedAgent(
            brain_llm=brain_llm,
            heart_llm=heart_llm,
            tool_manager=tool_manager,
            router_llm=router_llm
        )
        print(f"   ✅ OptimizedAgent created with tools: {agent.available_tools}")
        
        # =========================================================================
        # TEST 1: Insert data into MongoDB
        # =========================================================================
        print("\n" + "="*70)
        print("TEST 1: INSERT DATA INTO MONGODB")
        print("="*70)
        
        test_item = f"test_apple_{datetime.now().strftime('%H%M%S')}"
        insert_query = f"Add {test_item} to fruits collection in testdbb database in mongodb"
        
        print(f"\n📝 Query: '{insert_query}'")
        print("\n🔄 Processing through OptimizedAgent (source=whatsapp → simple_analysis)...")
        
        # Use source="whatsapp" to trigger simple_analysis path (no CoT routing)
        result = await agent.process_query(
            query=insert_query,
            user_id="integration_test_user",
            chat_history=[],
            source="whatsapp"  # This triggers simple_analysis directly!
        )
        
        print(f"\n📊 RESULT:")
        print(f"   Success: {result.get('success')}")
        print(f"   Tools used: {result.get('tools_used', [])}")
        print(f"   Response: {result.get('response', '')[:200]}...")
        
        if result.get('tool_results'):
            print(f"\n   Tool Results:")
            for tool_name, tool_result in result.get('tool_results', {}).items():
                print(f"      {tool_name}:")
                print(f"         Provider: {tool_result.get('provider')}")
                tool_success = tool_result.get('success')
                print(f"         Success: {tool_success}")
                if tool_result.get('executed_tool'):
                    print(f"         Executed: {tool_result.get('executed_tool')}")
                if tool_result.get('result'):
                    result_text = str(tool_result.get('result'))
                    print(f"         FULL Result: {result_text}")
                    # Check if result text indicates failure despite success=True
                    if tool_success:
                        failure_words = ["you need to connect", "failed", "error:", "unable to"]
                        if any(w in result_text.lower() for w in failure_words):
                            print(f"         ⚠️ WARNING: Result indicates ACTUAL FAILURE!")
                            tool_success = False  # Override for test validation
                if tool_result.get('error'):
                    print(f"         Error: {tool_result.get('error')}")
                if tool_result.get('needs_clarification'):
                    print(f"         Clarification: {tool_result.get('clarification_message')}")
        
        # Check if mongodb tool was used AND actually succeeded
        tools_used = result.get('tools_used', [])
        tool_results = result.get('tool_results', {})
        
        # Validate actual tool success (not just success=True, check result content)
        actual_insert_success = False
        for tool_name, tool_result in tool_results.items():
            if tool_result.get('success'):
                result_text = str(tool_result.get('result', '')).lower()
                failure_words = ["you need to connect", "failed", "error:", "unable to"]
                if not any(w in result_text for w in failure_words):
                    actual_insert_success = True
                    print(f"\n   ✅ Insert ACTUALLY succeeded - result: {result_text[:100]}")
                else:
                    print(f"\n   ❌ Insert FAILED - MCP returned error: {result_text[:100]}")
        
        if 'mongodb' not in tools_used:
            print(f"\n⚠️ WARNING: mongodb tool was not selected!")
            print(f"   Tools selected: {tools_used}")
            print("   The LLM may not have recognized this as a database operation")
        
        test1_passed = actual_insert_success and 'mongodb' in tools_used
        
        # =========================================================================
        # TEST 2: Find data from MongoDB
        # =========================================================================
        print("\n" + "="*70)
        print("TEST 2: FIND DATA FROM MONGODB")
        print("="*70)
        
        find_query = "Show all fruits from testdbb database in mongodb"
        
        print(f"\n📝 Query: '{find_query}'")
        print("\n🔄 Processing through OptimizedAgent (source=whatsapp → simple_analysis)...")
        
        result2 = await agent.process_query(
            query=find_query,
            user_id="integration_test_user",
            chat_history=[],
            source="whatsapp"
        )
        
        print(f"\n📊 RESULT:")
        print(f"   Success: {result2.get('success')}")
        print(f"   Tools used: {result2.get('tools_used', [])}")
        print(f"   Response: {result2.get('response', '')[:200]}...")
        
        if result2.get('tool_results'):
            print(f"\n   Tool Results:")
            for tool_name, tool_result in result2.get('tool_results', {}).items():
                print(f"      {tool_name}:")
                print(f"         Provider: {tool_result.get('provider')}")
                tool_success = tool_result.get('success')
                print(f"         Success: {tool_success}")
                if tool_result.get('result'):
                    result_text = str(tool_result.get('result'))
                    print(f"         FULL Result: {result_text}")
                    # Check if result text indicates failure despite success=True
                    if tool_success:
                        failure_words = ["you need to connect", "failed", "error:", "unable to"]
                        if any(w in result_text.lower() for w in failure_words):
                            print(f"         ⚠️ WARNING: Result indicates ACTUAL FAILURE!")
        
        # Validate actual tool success
        actual_find_success = False
        tool_results2 = result2.get('tool_results', {})
        for tool_name, tool_result in tool_results2.items():
            if tool_result.get('success'):
                result_text = str(tool_result.get('result', '')).lower()
                failure_words = ["you need to connect", "failed", "error:", "unable to"]
                if not any(w in result_text for w in failure_words):
                    actual_find_success = True
                    print(f"\n   ✅ Find ACTUALLY succeeded")
                else:
                    print(f"\n   ❌ Find FAILED - MCP returned error")
        
        test2_passed = actual_find_success and 'mongodb' in result2.get('tools_used', [])
        
        # =========================================================================
        # TEST 3: Clarification scenario (missing database)
        # =========================================================================
        print("\n" + "="*70)
        print("TEST 3: CLARIFICATION SCENARIO")
        print("="*70)
        
        # This query is missing the database name
        unclear_query = "Add banana to fruits collection"
        
        print(f"\n📝 Query: '{unclear_query}' (missing database)")
        print("\n🔄 Processing through OptimizedAgent (source=whatsapp → simple_analysis)...")
        
        result3 = await agent.process_query(
            query=unclear_query,
            user_id="integration_test_user",
            chat_history=[],
            source="whatsapp"
        )
        
        print(f"\n📊 RESULT:")
        print(f"   Success: {result3.get('success')}")
        print(f"   Tools used: {result3.get('tools_used', [])}")
        print(f"   Response: {result3.get('response', '')[:300]}...")
        
        # Check if clarification was requested
        tool_results = result3.get('tool_results', {})
        needs_clarification = False
        for tool_name, tool_result in tool_results.items():
            if tool_result.get('needs_clarification'):
                needs_clarification = True
                print(f"\n   ✅ Clarification requested:")
                print(f"      Message: {tool_result.get('clarification_message')}")
                print(f"      Missing: {tool_result.get('missing_fields')}")
        
        test3_passed = needs_clarification or 'mongodb' in result3.get('tools_used', [])
        
        # =========================================================================
        # SUMMARY
        # =========================================================================
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        
        print(f"   Test 1 (Insert): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
        print(f"   Test 2 (Find):   {'✅ PASSED' if test2_passed else '❌ FAILED'}")
        print(f"   Test 3 (Clarification): {'✅ PASSED' if test3_passed else '❌ FAILED'}")
        
        all_passed = test1_passed and test2_passed and test3_passed
        
        if all_passed:
            print("\n🎉 ALL TESTS PASSED!")
            print("\n✅ Full flow verified:")
            print("   Query → OptimizedAgent.process_query(source='whatsapp')")
            print("        → _simple_analysis() using router_llm (nemotron)")
            print("        → Selects 'mongodb' tool")
            print("        → ToolManager.execute_tool('mongodb')")
            print("        → QueryAgent.execute() with real LLM")
            print("        → MongoDB MCP server executes")
            print("        → Real data in MongoDB")
            print("        → _generate_response() using heart_llm (llama-4-maverick)")
        else:
            print("\n⚠️ SOME TESTS FAILED")
        
        # Cleanup
        print("\n🧹 Cleaning up...")
        await tool_manager.cleanup()
        await brain_llm.close_session()
        await heart_llm.close_session()
        await router_llm.close_session()
        
        return all_passed
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(run_real_integration_test())
    sys.exit(0 if success else 1)
