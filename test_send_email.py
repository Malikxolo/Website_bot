"""
Test script to send an email via Zapier Gmail integration.
"""
import asyncio
import os
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

async def send_test_email():
    from core.mcp import ZapierToolManager, MCPSecurityManager
    
    print('🔧 Initializing Zapier...')
    security = MCPSecurityManager()
    manager = ZapierToolManager(security)
    
    try:
        # Initialize connection
        initialized = await manager.initialize()
        if not initialized:
            print('❌ Failed to initialize Zapier')
            return
        
        print('✅ Zapier initialized')
        print(f'📋 Available tools: {manager.get_tool_names()}')
        
        # Get the tool schema to see what params are needed
        schema = manager.get_tool_schema('zapier_gmail_send_email')
        if schema:
            print(f'\n📝 Tool schema:')
            print(f'   Description: {schema.get("description", "N/A")[:100]}...')
            print(f'   Required: {schema.get("required", [])}')
        
        # Send email using zapier_gmail_send_email
        print('\n📧 Sending test email to faizanmalik185@gmail.com...')
        result = await manager.execute(
            tool_name='zapier_gmail_send_email',
            params={
                'instructions': 'Send an email with subject "Test from CS-Agent via Zapier MCP" and body "Hi"',
                'to': ['faizanmalik185@gmail.com'],
                'subject': 'Test from CS-Agent via Zapier MCP',
                'body': 'Hi'
            }
        )
        
        print(f'\n📬 Result:')
        print(f'   Success: {result.get("success", False)}')
        print(f'   Tool: {result.get("tool")}')
        if result.get('error'):
            print(f'   Error: {result.get("error")}')
        if result.get('result'):
            print(f'   Response: {result.get("result")}')
            
    except Exception as e:
        print(f'❌ Error: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await manager.close()
        print('\n✅ Connection closed')

if __name__ == '__main__':
    asyncio.run(send_test_email())
