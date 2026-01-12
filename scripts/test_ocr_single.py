import asyncio
from src.models import Database
from src.processor import DocumentProcessor
import tomli

async def test_single_doc():
    with open('config.toml', 'rb') as f:
        config = tomli.load(f)
    
    db = Database(config['app']['db_path'])
    processor = DocumentProcessor(config, db)
    
    # 获取第一个pending文档
    pending = db.get_pending_documents()
    if pending:
        doc_id = pending[0]['id']
        print(f'测试处理文档 ID: {doc_id}')
        await processor.process_document(doc_id)
        
        # 检查处理结果
        doc = db.get_document(doc_id)
        print(f'OCR状态: {doc[\"ocr_status\"]}')
        print(f'LLM状态: {doc[\"llm_status\"]}')
        if doc['ocr_text']:
            print(f'OCR文本长度: {len(doc[\"ocr_text\"])} 字符')
            print(f'OCR文本预览: {doc[\"ocr_text\"][:300]}')
        if doc.get('properties'):
            print(f'提取的属性数量: {len(doc[\"properties\"])}')
            print(f'属性: {doc[\"properties\"]}')
    else:
        print('没有待处理的文档')
    
    processor.close()

if __name__ == '__main__':
    asyncio.run(test_single_doc())
