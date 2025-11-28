"""
Debug test for Zapier tool execution and response handling.

Tests three scenarios:
1. Email with valid address - should succeed
2. Email without address - should get clarification question
3. Query for non-existent tool - should handle gracefully
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


async def test_zapier_scenarios():
    """Test various Zapier scenarios to debug response handling."""
    print("=" * 70)
    print("ZAPIER RESPONSE HANDLING DEBUG")
    print("=" * 70)
    
    from core.config import Config
    from core.llm_client import LLMClient
    from core.tools import ToolManager
    from core.optimized_agent import OptimizedAgent
    from api.global_config import settings
    
    config = Config()
    providers = config.get_available_providers()
    
    if "openrouter" not in providers:
        print("X OpenRouter not configured")
        return
    
    # Use models from .env - Brain: nvidia/llama-3.3-nemotron-super-49b-v1.5
    brain_model = os.getenv("BRAIN_LLM_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5")
    heart_model = os.getenv("HEART_LLM_MODEL", "meta-llama/llama-4-maverick")
    
    print(f"[CONFIG] Brain Model: {brain_model}")
    print(f"[CONFIG] Heart Model: {heart_model}")
    print(f"[CONFIG] Language Detection Enabled: {config.language_detection_enabled}")
    
    brain_config = config.create_llm_config("openrouter", brain_model)
    heart_config = config.create_llm_config("openrouter", heart_model)
    
    brain_llm = LLMClient(brain_config)
    heart_llm = LLMClient(heart_config)
    
    # Initialize Indic LLM for Sarvam (Indian language responses)
    indic_llm = None
    if settings.indic_provider and settings.indic_model:
        try:
            indic_model_config = config.create_llm_config(
                provider=settings.indic_provider,
                model=settings.indic_model,
                max_tokens=1000
            )
            indic_llm = LLMClient(indic_model_config)
            print(f"[CONFIG] Indic LLM: {settings.indic_provider}/{settings.indic_model} ✅")
        except Exception as e:
            print(f"[CONFIG] Indic LLM initialization failed: {e}")
            indic_llm = None
    
    # Initialize language detector if enabled
    language_detector_llm = None
    if config.language_detection_enabled:
        try:
            lang_detect_config = config.create_language_detection_config()
            language_detector_llm = LLMClient(lang_detect_config)
            print(f"[CONFIG] Language Detector: {config.language_detection_provider}/{config.language_detection_model} ✅")
        except Exception as e:
            print(f"[CONFIG] Language detection initialization failed: {e}. Continuing without language detection.")
            language_detector_llm = None
    
    tool_manager = ToolManager(config, heart_llm)
    await tool_manager.initialize_zapier_async()
    
    # Initialize agent with language detection components
    agent = OptimizedAgent(
        brain_llm=brain_llm,
        heart_llm=heart_llm,
        tool_manager=tool_manager,
        router_llm=None,  # No routing layer for this test
        indic_llm=indic_llm,
        language_detector_llm=language_detector_llm
    )
    
    print(f"\n[TOOLS] Available Tools: {agent.available_tools}")
    print(f"[ZAPIER] Zapier Tools: {tool_manager.get_zapier_tools()}")
    
    # Test scenarios - Using unique messages to bypass cache
    import random
    unique_id = random.randint(1000, 9999)
    
    test_cases = [
        # {
        #     "name": "1 - Valid Email with Address",
        #     "query": f"Send an email to faizanmalik185@gmail.com ,aakashisjesus@gmail.com,tiwarianmol173@gmail.com and vasthana@foodnests.com with subject 'NL Test {unique_id}' and body 'Testing natural language instructions {unique_id}'",
        #     "expected": "Should succeed and send email"
        # },
        # {
        #     "name": "4 - Google Calendar: Create Event",
        #     "tool": "Google Calendar",
        #     "query": f"Create a calendar event for tomorrow at 2 PM titled 'Team Meeting {unique_id}' for 1 hour",
        #     "expected": "Should create calendar event",
        #     "note": "Enable: Google Calendar - Create Detailed Event action"
        # }
        {
            "name": "2 - Microsoft Excel: Create Workbook and Add Row",
            "tool": "Microsoft Excel",
            "query": f"Create a new Microsoft Excel workbook named 'Sales Report {unique_id}' and then add a row with Name='John Doe', Amount=5000, Date='2025-11-28'",
            "expected": "Should create Excel workbook and add row",
            "note": "Enable: Microsoft Excel create workbook and add row to table"
        },
    ]
    
    for test in test_cases:
        print(f"\n{'='*70}")
        print(f"TEST: {test['name']}")
        print(f"Query: {test['query']}")
        print(f"Expected: {test['expected']}")
        print("=" * 70)
        
        try:
            # Use source="whatsapp" to use simple analysis (no routing layer)
            result = await agent.process_query(
                query=test['query'],
                chat_history=[],
                user_id="test_debug",
                source="whatsapp"
            )
            
            print(f"\n[RESULT]:")
            print(f"   Response: {result.get('response', 'NO RESPONSE')[:300]}...")
            print(f"   Tools Used: {result.get('tools_used', [])}")
            
            # Show tool results in detail
            tool_results = result.get('tool_results', {})
            if tool_results:
                print(f"\n   [TOOL RESULTS]:")
                for tool_name, tool_result in tool_results.items():
                    print(f"      Tool: {tool_name}")
                    if isinstance(tool_result, dict):
                        print(f"         success: {tool_result.get('success')}")
                        print(f"         error: {tool_result.get('error', 'None')}")
                        print(f"         needs_clarification: {tool_result.get('needs_clarification', False)}")
                        if 'result' in tool_result:
                            result_preview = str(tool_result['result'])[:200]
                            print(f"         result: {result_preview}...")
                    else:
                        print(f"         raw: {str(tool_result)[:200]}")
            
        except Exception as e:
            print(f"\n[ERROR]: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
        
        # Small delay between tests
        await asyncio.sleep(2)
    
    # Cleanup
    print("\n[CLEANUP] Cleaning up...")
    await brain_llm.close_session()
    await heart_llm.close_session()
    if indic_llm:
        await indic_llm.close_session()
    if language_detector_llm:
        await language_detector_llm.close_session()
    if tool_manager._zapier_manager:
        await tool_manager._zapier_manager.close()
    
    print("\n" + "=" * 70)
    print("DEBUG TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_zapier_scenarios())
