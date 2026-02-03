"""
文档索引构建器

扫描项目文档和 Sphinx 文档，构建可搜索的索引
"""
import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Iterator

from .config import PROJECT_ROOT, DOC_SOURCES, KEY_INDEX_FILES, SEARCH_CONFIG
from .parsers import MarkdownParser, RstParser


class DocIndex:
    """文档索引"""
    
    def __init__(self):
        self._docs: Dict[str, List[Dict]] = {
            "project": [],
            "sphinx": [],
        }
        self._built = False
    
    def build(self, force: bool = False) -> None:
        """构建文档索引"""
        if self._built and not force:
            return
        
        # 扫描项目文档
        self._docs["project"] = list(self._scan_category("project"))
        
        # 扫描 Sphinx 文档
        self._docs["sphinx"] = list(self._scan_category("sphinx"))
        
        self._built = True
    
    def _scan_category(self, category: str) -> Iterator[Dict]:
        """扫描指定类别的文档"""
        config = DOC_SOURCES.get(category)
        if not config:
            return
        
        extensions = config.get("extensions", [".md", ".rst"])
        exclude_patterns = config.get("exclude_patterns", [])
        
        for rel_path in config.get("paths", []):
            scan_path = PROJECT_ROOT / rel_path
            if not scan_path.exists():
                continue
            
            for file_path in scan_path.rglob("*"):
                if not file_path.is_file():
                    continue
                
                if file_path.suffix not in extensions:
                    continue
                
                # 检查排除模式
                rel_file = str(file_path.relative_to(PROJECT_ROOT))
                if any(fnmatch.fnmatch(rel_file, pattern) 
                       for pattern in exclude_patterns):
                    continue
                
                # 解析文档
                doc_info = self._parse_doc(file_path)
                if doc_info:
                    doc_info["category"] = category
                    yield doc_info
    
    def _parse_doc(self, file_path: Path) -> Optional[Dict]:
        """解析单个文档"""
        try:
            if file_path.suffix == ".md":
                parser = MarkdownParser(file_path)
            elif file_path.suffix == ".rst":
                parser = RstParser(file_path)
            else:
                return None
            
            info = parser.to_dict()
            info["rel_path"] = str(file_path.relative_to(PROJECT_ROOT))
            return info
            
        except Exception as e:
            return {
                "path": str(file_path),
                "rel_path": str(file_path.relative_to(PROJECT_ROOT)),
                "title": file_path.stem,
                "error": str(e),
            }
    
    def list_topics(self, category: str = "all") -> List[Dict]:
        """列出文档主题"""
        self.build()
        
        if category == "all":
            result = []
            result.extend(self._docs["project"])
            result.extend(self._docs["sphinx"])
            return result
        
        return self._docs.get(category, [])
    
    def search(self, query: str, category: str = "all", 
               max_results: int = None) -> List[Dict]:
        """搜索文档"""
        self.build()
        
        if max_results is None:
            max_results = SEARCH_CONFIG["max_results"]
        
        query_lower = query.lower()
        results = []
        
        docs = self.list_topics(category)
        
        for doc in docs:
            score = 0
            snippet = None
            
            # 标题匹配（权重高）
            title = doc.get("title", "").lower()
            if query_lower in title:
                score += 10
                if title == query_lower:
                    score += 5  # 精确匹配加分
            
            # 路径匹配
            rel_path = doc.get("rel_path", "").lower()
            if query_lower in rel_path:
                score += 3
            
            # 标题层级匹配
            headings = doc.get("headings", [])
            for heading in headings:
                if query_lower in heading.get("text", "").lower():
                    score += 2
                    break
            
            # 内容匹配（需要重新解析获取摘要）
            if score == 0:
                file_path = PROJECT_ROOT / doc.get("rel_path", "")
                if file_path.exists():
                    try:
                        if file_path.suffix == ".md":
                            parser = MarkdownParser(file_path)
                        else:
                            parser = RstParser(file_path)
                        
                        snippet = parser.get_snippet(
                            query, 
                            SEARCH_CONFIG["snippet_length"]
                        )
                        if snippet:
                            score += 1
                    except Exception:
                        pass
            
            if score > 0:
                result = doc.copy()
                result["score"] = score
                if snippet:
                    result["snippet"] = snippet
                results.append(result)
        
        # 按分数排序
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return results[:max_results]
    
    def read_doc(self, rel_path: str) -> Optional[Dict]:
        """读取指定文档的完整内容"""
        file_path = PROJECT_ROOT / rel_path
        
        if not file_path.exists():
            return None
        
        try:
            if file_path.suffix == ".md":
                parser = MarkdownParser(file_path)
            elif file_path.suffix == ".rst":
                parser = RstParser(file_path)
            else:
                # 尝试作为纯文本读取
                content = file_path.read_text(encoding='utf-8')
                return {
                    "path": rel_path,
                    "title": file_path.stem,
                    "content": content,
                }
            
            return {
                "path": rel_path,
                "title": parser.title,
                "headings": parser.headings,
                "content": parser.content,
                "text_content": parser.get_text_content(),
            }
            
        except Exception as e:
            return {
                "path": rel_path,
                "error": str(e),
            }
    
    def get_project_index(self) -> Dict:
        """获取项目关键索引"""
        self.build()
        
        result = {
            "key_files": [],
            "summary": {
                "project_docs": len(self._docs["project"]),
                "sphinx_docs": len(self._docs["sphinx"]),
            },
        }
        
        for rel_path in KEY_INDEX_FILES:
            file_path = PROJECT_ROOT / rel_path
            if file_path.exists():
                doc_info = self.read_doc(rel_path)
                if doc_info and "error" not in doc_info:
                    # 只返回摘要，不返回完整内容
                    result["key_files"].append({
                        "path": rel_path,
                        "title": doc_info.get("title"),
                        "headings": doc_info.get("headings", [])[:10],  # 只取前10个标题
                    })
        
        return result


# 全局索引实例（单例模式）
_index_instance: Optional[DocIndex] = None


def get_index() -> DocIndex:
    """获取文档索引实例"""
    global _index_instance
    if _index_instance is None:
        _index_instance = DocIndex()
    return _index_instance
