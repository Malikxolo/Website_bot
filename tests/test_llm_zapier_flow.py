"""
End-to-End LLM Test for OptimizedAgent with Zapier Tool Execution

This test verifies the FULL LLM FLOW:
1. User gives natural language query: "Send email to X with subject Y"
2. LLM analyzes the query and decides which tool to use
3. LLM extracts/generates correct parameters
4. Tool is executed (real email sent)
5. Response is generated

This tests how the LLM behaves with Zapier tools - the main focus!

Run: python tests/test_llm_zapier_flow.py
"""

import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Configure logging to see LLM decisions
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


async def test_llm_email_flow():
    """
    Test the FULL LLM flow for sending email via Zapier.
    
    This simulates a real user query and lets the LLM:
    1. Analyze the intent
    2. Select the appropriate tool (zapier_gmail_send_email)
    3. Generate parameters
    4. Execute the tool
    5. Generate response
    """
    print("=" * 70)
    print("🧠 END-TO-END LLM TEST: Natural Language → Zapier Email")
    print("=" * 70)
    
    from core.config import Config
    from core.llm_client import LLMClient
    from core.tools import ToolManager
    from core.optimized_agent import OptimizedAgent
    
    # Step 1: Initialize all components
    print("\n📦 Step 1: Initializing components...")
    
    config = Config()
    providers = config.get_available_providers()
    print(f"   Available LLM providers: {providers}")
    
    # Use OpenRouter for both brain and heart to avoid API compatibility issues
    # OpenRouter supports the full provider options
    if "openrouter" not in providers:
        print("❌ OpenRouter not configured. This test requires OpenRouter for proper LLM execution.")
        return
    
    brain_provider = "openrouter"
    heart_provider = "openrouter"
    
    # Use a fast model for analysis
    brain_model = "qwen/qwen3-next-80b-a3b-thinking"
    heart_model = "meta-llama/llama-3.3-70b-instruct"  # Fast model for responses
    
    print(f"   Brain LLM: {brain_provider}/{brain_model}")
    print(f"   Heart LLM: {heart_provider}/{heart_model}")
    
    brain_config = config.create_llm_config(brain_provider, brain_model)
    heart_config = config.create_llm_config(heart_provider, heart_model)
    
    brain_llm = LLMClient(brain_config)
    heart_llm = LLMClient(heart_config)
    
    # Initialize tool manager with Zapier
    tool_manager = ToolManager(config, heart_llm)
    
    print("\n🔌 Step 2: Initializing Zapier MCP...")
    zapier_ok = await tool_manager.initialize_zapier_async()
    
    if not zapier_ok:
        print("❌ Zapier not configured. Set MCP_ENABLED=true and ZAPIER_MCP_SERVER_URL")
        return
    
    zapier_tools = tool_manager.get_zapier_tools()
    print(f"   ✅ Zapier initialized with {len(zapier_tools)} tools:")
    for tool in zapier_tools:
        print(f"      • {tool}")
    
    # Create OptimizedAgent
    print("\n🤖 Step 3: Creating OptimizedAgent...")
    agent = OptimizedAgent(
        brain_llm=brain_llm,
        heart_llm=heart_llm,
        tool_manager=tool_manager
    )
    print(f"   ✅ Agent created with tools: {agent.available_tools}")
    
    # Show dynamic tools prompt
    print("\n📋 Step 4: Dynamic Tools Prompt (what LLM sees):")
    print("-" * 50)
    print(agent._get_tools_prompt_section())
    print("-" * 50)
    
    # Step 5: Send natural language query
    import time
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # THE ACTUAL TEST QUERY - Natural language!
    test_query = f"""send  mail to tiwarianmol173@gmail.com saying congratulations for your zapier integration working"""
    
    print(f"\n📨 Step 5: Sending query to LLM...")
    print(f"   Query: \"{test_query[:100]}...\"")
    print("\n" + "=" * 70)
    print("🧠 LLM PROCESSING (watch the logs for tool selection)...")
    print("=" * 70 + "\n")
    
    try:
        # This is the REAL test - process_query will:
        # 1. Analyze with Brain LLM
        # 2. Select tools (should pick zapier_gmail_send_email)
        # 3. Execute tools
        # 4. Generate response with Heart LLM
        result = await agent.process_query(
            query=test_query,
            chat_history=[],
            user_id="test_user1_llm",
            mode="test",
            source="api"  # Not whatsapp, so it uses full analysis
        )
        
        print("\n" + "=" * 70)
        print("📊 RESULT:")
        print("=" * 70)
        
        # Check if successful
        response = result.get("response", "")
        tools_used = result.get("tools_used", [])
        tool_results = result.get("tool_results", {})
        
        print(f"\n✅ Response: {response[:500]}...")
        print(f"\n🔧 Tools Used: {tools_used}")
        
        # Check if Zapier tool was used
        zapier_used = any("zapier" in str(t).lower() for t in tools_used)
        
        if zapier_used:
            print("\n✅ SUCCESS: LLM correctly selected and used Zapier Gmail tool!")
            print("   → Check faizanmalik185@gmail.com for the email")
        else:
            print("\n⚠️ WARNING: Zapier tool was NOT used")
            print(f"   → Tools used: {tools_used}")
            print(f"   → Tool results: {tool_results}")
        
        # Show full result for debugging
        print(f"\n📋 Full Result Keys: {result.keys()}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        await brain_llm.close_session()
        await heart_llm.close_session()
        if tool_manager._zapier_manager:
            await tool_manager._zapier_manager.close()
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


async def test_multiple_queries():
    """Test multiple different queries to see how LLM handles each"""
    print("\n" + "=" * 70)
    print("🧪 MULTIPLE QUERY TEST")
    print("=" * 70)
    
    from core.config import Config
    from core.llm_client import LLMClient
    from core.tools import ToolManager
    from core.optimized_agent import OptimizedAgent
    
    config = Config()
    providers = config.get_available_providers()
    
    brain_provider = "openrouter" if "openrouter" in providers else providers[0]
    heart_provider = "groq" if "groq" in providers else brain_provider
    
    brain_config = config.create_llm_config(brain_provider, config.get_available_models(brain_provider)[0])
    heart_config = config.create_llm_config(heart_provider, config.get_available_models(heart_provider)[0])
    
    brain_llm = LLMClient(brain_config)
    heart_llm = LLMClient(heart_config)
    tool_manager = ToolManager(config, heart_llm)
    
    await tool_manager.initialize_zapier_async()
    
    agent = OptimizedAgent(
        brain_llm=brain_llm,
        heart_llm=heart_llm,
        tool_manager=tool_manager
    )
    
    # Test queries - each should trigger different tool selection
    test_queries = [
        # Should trigger zapier_gmail_send_email
        "Please send an email to tiwarianmol173@gmail.com saying 'Test from AI - Query 1'",
        
        # Should trigger web_search
        # "What's the weather in Lahore today?",
        
        # Should NOT trigger any external tool
        # "What is 25 * 4 + 100?",
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'=' * 50}")
        print(f"Query {i}: {query[:60]}...")
        print('=' * 50)
        
        try:
            result = await agent.process_query(
                query=query,
                chat_history=[],
                user_id=f"test_user_{i}",
                source="api"
            )
            
            tools_used = result.get("tools_used", [])
            response = result.get("response", "")[:200]
            
            print(f"Tools: {tools_used}")
            print(f"Response: {response}...")
            
        except Exception as e:
            print(f"Error: {e}")
    
    # Cleanup
    await brain_llm.close_session()
    await heart_llm.close_session()
    if tool_manager._zapier_manager:
        await tool_manager._zapier_manager.close()


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║     END-TO-END LLM + ZAPIER TEST                                     ║
║                                                                       ║
║     Tests the FULL flow:                                             ║
║     1. Natural language query → LLM                                  ║
║     2. LLM analyzes intent & selects tool                            ║
║     3. LLM generates parameters for Zapier                           ║
║     4. Tool executes (real email sent!)                              ║
║     5. LLM generates response                                        ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    asyncio.run(test_llm_email_flow())
