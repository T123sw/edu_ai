"""
课程文件存储管理模块
统一管理课程相关的所有文件，包括：
- 课程基础信息（JSON）
- 课程知识库文件（文档、PDF等）
- 教师生成的教学资料
"""
import os
import json
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

# 课程存储根目录（默认在api目录同级）
COURSE_STORAGE_ROOT = Path(__file__).resolve().parents[2] / 'course_data'

# 目录结构：
# course_data/
#   ├── courses/                          # 所有课程数据
#   │   └── {course_id}/                  # 单个课程目录
#   │       ├── course_info.json          # 课程基础信息
#   │       ├── knowledge_base/           # 课程知识库 (L1)
#   │       │   ├── documents/            # 文档文件
#   │       │   └── index.json            # 知识库索引文件
#   │       ├── generated_materials/      # 教师生成的教学资料
#   │       │   ├── audio/                # 音频概览
#   │       │   ├── lesson_plans/         # 教案生成
#   │       │   ├── graphs/               # 思维导图
#   │       │   ├── reports/              # 报告
#   │       │   ├── blogs/                # 教学博客
#   │       │   └── quizzes/              # 测验
#   │       └── metadata.json             # 课程元数据（创建时间、更新时间等）


class CourseStorageManager:
    """课程存储管理器"""
    
    def __init__(self, root_path: Optional[str] = None):
        """
        初始化课程存储管理器
        
        Args:
            root_path: 存储根目录路径（字符串或Path），默认为 COURSE_STORAGE_ROOT
        """
        if root_path:
            self.root_path = Path(root_path)
        else:
            # 尝试从环境变量获取，否则使用默认路径
            env_path = os.getenv("COURSE_STORAGE_ROOT")
            self.root_path = Path(env_path) if env_path else COURSE_STORAGE_ROOT
        self.courses_dir = self.root_path / 'courses'
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保必要的目录结构存在"""
        self.courses_dir.mkdir(parents=True, exist_ok=True)
    
    def get_course_dir(self, course_id: str) -> Path:
        """
        获取课程目录路径
        
        Args:
            course_id: 课程ID
            
        Returns:
            课程目录的Path对象
        """
        return self.courses_dir / course_id
    
    def create_course_structure(self, course_id: str) -> Path:
        """
        创建课程目录结构
        
        Args:
            course_id: 课程ID
            
        Returns:
            课程目录的Path对象
        """
        course_dir = self.get_course_dir(course_id)
        
        # 创建主要目录
        (course_dir / 'knowledge_base' / 'documents').mkdir(parents=True, exist_ok=True)
        (course_dir / 'generated_materials' / 'audio').mkdir(parents=True, exist_ok=True)
        (course_dir / 'generated_materials' / 'lesson_plans').mkdir(parents=True, exist_ok=True)
        (course_dir / 'generated_materials' / 'graphs').mkdir(parents=True, exist_ok=True)
        (course_dir / 'generated_materials' / 'reports').mkdir(parents=True, exist_ok=True)
        (course_dir / 'generated_materials' / 'blogs').mkdir(parents=True, exist_ok=True)
        (course_dir / 'generated_materials' / 'quizzes').mkdir(parents=True, exist_ok=True)
        
        # 创建元数据文件
        metadata = {
            'course_id': course_id,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        }
        self.save_course_metadata(course_id, metadata)
        
        # 创建知识库索引文件
        self.save_knowledge_base_index(course_id, [])
        
        return course_dir
    
    def save_course_info(self, course_id: str, course_info: Dict[str, Any]) -> bool:
        """
        保存课程基础信息
        
        Args:
            course_id: 课程ID
            course_info: 课程信息字典
            
        Returns:
            是否保存成功
        """
        try:
            course_dir = self.get_course_dir(course_id)
            course_dir.mkdir(parents=True, exist_ok=True)
            
            info_file = course_dir / 'course_info.json'
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(course_info, f, ensure_ascii=False, indent=2)
            
            # 更新元数据
            metadata = self.get_course_metadata(course_id)
            metadata['updated_at'] = datetime.now().isoformat()
            self.save_course_metadata(course_id, metadata)
            
            return True
        except Exception as e:
            print(f"Error saving course info: {e}")
            return False
    
    def get_course_info(self, course_id: str) -> Optional[Dict[str, Any]]:
        """
        获取课程基础信息
        
        Args:
            course_id: 课程ID
            
        Returns:
            课程信息字典，如果不存在则返回None
        """
        try:
            info_file = self.get_course_dir(course_id) / 'course_info.json'
            if not info_file.exists():
                return None
            
            with open(info_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading course info: {e}")
            return None
    
    def save_course_metadata(self, course_id: str, metadata: Dict[str, Any]) -> bool:
        """
        保存课程元数据
        
        Args:
            course_id: 课程ID
            metadata: 元数据字典
            
        Returns:
            是否保存成功
        """
        try:
            metadata_file = self.get_course_dir(course_id) / 'metadata.json'
            metadata_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving course metadata: {e}")
            return False
    
    def get_course_metadata(self, course_id: str) -> Dict[str, Any]:
        """
        获取课程元数据
        
        Args:
            course_id: 课程ID
            
        Returns:
            元数据字典
        """
        metadata_file = self.get_course_dir(course_id) / 'metadata.json'
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        
        # 返回默认元数据
        return {
            'course_id': course_id,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        }
    
    def save_knowledge_base_file(self, course_id: str, file_data: bytes, filename: str) -> Optional[str]:
        """
        保存知识库文件
        
        Args:
            course_id: 课程ID
            file_data: 文件数据（字节）
            filename: 文件名
            
        Returns:
            保存的文件路径（相对路径），如果失败则返回None
        """
        try:
            kb_documents_dir = self.get_course_dir(course_id) / 'knowledge_base' / 'documents'
            kb_documents_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = kb_documents_dir / filename
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            # 更新知识库索引
            index = self.get_knowledge_base_index(course_id)
            file_info = {
                'id': f"doc-{datetime.now().timestamp()}",
                'filename': filename,
                'path': f"knowledge_base/documents/{filename}",
                'size': len(file_data),
                'uploaded_at': datetime.now().isoformat(),
            }
            index.append(file_info)
            self.save_knowledge_base_index(course_id, index)
            
            return str(file_path.relative_to(self.get_course_dir(course_id)))
        except Exception as e:
            print(f"Error saving knowledge base file: {e}")
            return None
    
    def get_knowledge_base_index(self, course_id: str) -> List[Dict[str, Any]]:
        """
        获取知识库索引
        
        Args:
            course_id: 课程ID
            
        Returns:
            知识库文件索引列表
        """
        index_file = self.get_course_dir(course_id) / 'knowledge_base' / 'index.json'
        if index_file.exists():
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return []
    
    def save_knowledge_base_index(self, course_id: str, index: List[Dict[str, Any]]) -> bool:
        """
        保存知识库索引
        
        Args:
            course_id: 课程ID
            index: 索引列表
            
        Returns:
            是否保存成功
        """
        try:
            index_file = self.get_course_dir(course_id) / 'knowledge_base' / 'index.json'
            index_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving knowledge base index: {e}")
            return False
    
    def save_knowledge_graph(self, course_id: str, graph_data: Dict[str, Any]) -> bool:
        """
        保存课程知识图谱数据
        
        Args:
            course_id: 课程ID
            graph_data: 知识图谱数据（字典）
            
        Returns:
            是否保存成功
        """
        try:
            course_dir = self.get_course_dir(course_id)
            graph_file = course_dir / 'knowledge_graph.json'
            graph_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(graph_file, 'w', encoding='utf-8') as f:
                json.dump(graph_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving knowledge graph: {e}")
            return False
    
    def get_knowledge_graph(self, course_id: str) -> Optional[Dict[str, Any]]:
        """
        获取课程知识图谱数据
        
        Args:
            course_id: 课程ID
            
        Returns:
            知识图谱数据（字典），如果不存在则返回None
        """
        try:
            course_dir = self.get_course_dir(course_id)
            graph_file = course_dir / 'knowledge_graph.json'
            
            if not graph_file.exists():
                return None
            
            with open(graph_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading knowledge graph: {e}")
            return None
    
    def save_generated_material(self, course_id: str, material_type: str, material_id: str, 
                                material_data: Dict[str, Any], file_data: Optional[bytes] = None) -> bool:
        """
        保存生成的教学资料
        
        Args:
            course_id: 课程ID
            material_type: 资料类型（audio, lesson_plan, graph, report, blog, quiz）
            material_id: 资料ID
            material_data: 资料数据（字典）
            file_data: 可选的附件文件数据
            
        Returns:
            是否保存成功
        """
        try:
            # 确定保存目录
            type_mapping = {
                'audio': 'audio',
                'lesson_plan': 'lesson_plans',
                'graph': 'graphs',
                'report': 'reports',
                'blog': 'blogs',
                'quiz': 'quizzes',
            }
            
            material_dir = self.get_course_dir(course_id) / 'generated_materials' / type_mapping.get(material_type, 'others')
            material_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存资料JSON
            material_file = material_dir / f"{material_id}.json"
            with open(material_file, 'w', encoding='utf-8') as f:
                json.dump(material_data, f, ensure_ascii=False, indent=2)
            
            # 如果有附件文件，保存文件
            if file_data:
                # 根据material_data中的文件类型确定扩展名
                file_ext = material_data.get('file_extension', '.txt')
                file_path = material_dir / f"{material_id}{file_ext}"
                with open(file_path, 'wb') as f:
                    f.write(file_data)
                material_data['file_path'] = str(file_path.relative_to(self.get_course_dir(course_id)))

                # 重新写入 JSON，确保 file_path 等字段保存
                with open(material_file, 'w', encoding='utf-8') as f:
                    json.dump(material_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving generated material: {e}")
            return False
    
    def get_generated_material(self, course_id: str, material_type: str, material_id: str) -> Optional[Dict[str, Any]]:
        """
        获取生成的教学资料
        
        Args:
            course_id: 课程ID
            material_type: 资料类型
            material_id: 资料ID
            
        Returns:
            资料数据字典，如果不存在则返回None
        """
        try:
            type_mapping = {
                'audio': 'audio',
                'lesson_plan': 'lesson_plans',
                'graph': 'graphs',
                'report': 'reports',
                'blog': 'blogs',
                'quiz': 'quizzes',
            }
            
            material_file = (self.get_course_dir(course_id) / 'generated_materials' / 
                           type_mapping.get(material_type, 'others') / f"{material_id}.json")
            
            if material_file.exists():
                with open(material_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading generated material: {e}")
        
        return None
    
    def list_generated_materials(self, course_id: str, material_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出所有生成的教学资料
        
        Args:
            course_id: 课程ID
            material_type: 可选的资料类型筛选
            
        Returns:
            资料列表
        """
        materials = []
        
        try:
            generated_materials_dir = self.get_course_dir(course_id) / 'generated_materials'
            
            if material_type:
                type_mapping = {
                    'audio': 'audio',
                    'lesson_plan': 'lesson_plans',
                    'graph': 'graphs',
                    'report': 'reports',
                    'blog': 'blogs',
                    'quiz': 'quizzes',
                }
                type_dir = generated_materials_dir / type_mapping.get(material_type, 'others')
                if type_dir.exists():
                    for json_file in type_dir.glob('*.json'):
                        try:
                            with open(json_file, 'r', encoding='utf-8') as f:
                                material_data = json.load(f)
                                material_data['material_id'] = json_file.stem
                                materials.append(material_data)
                        except Exception:
                            continue
            else:
                # 列出所有类型的资料
                for type_dir in generated_materials_dir.iterdir():
                    if type_dir.is_dir():
                        for json_file in type_dir.glob('*.json'):
                            try:
                                with open(json_file, 'r', encoding='utf-8') as f:
                                    material_data = json.load(f)
                                    material_data['material_id'] = json_file.stem
                                    materials.append(material_data)
                            except Exception:
                                continue
        except Exception as e:
            print(f"Error listing generated materials: {e}")
        
        return materials
    
    def delete_generated_material(self, course_id: str, material_type: str, material_id: str) -> bool:
        """
        删除指定的生成材料
        
        Args:
            course_id: 课程ID
            material_type: 材料类型
            material_id: 材料ID
            
        Returns:
            是否删除成功
        """
        try:
            type_mapping = {
                'audio': 'audio',
                'lesson_plan': 'lesson_plans',
                'graph': 'graphs',
                'report': 'reports',
                'blog': 'blogs',
                'quiz': 'quizzes',
            }
            
            generated_materials_dir = self.get_course_dir(course_id) / 'generated_materials'
            type_dir = generated_materials_dir / type_mapping.get(material_type, 'others')
            
            if type_dir.exists():
                material_file = type_dir / f"{material_id}.json"
                if material_file.exists():
                    material_file.unlink()
                    return True
            return False
        except Exception as e:
            print(f"Error deleting generated material: {e}")
            return False
    
    def delete_course(self, course_id: str) -> bool:
        """
        删除课程及其所有数据
        
        Args:
            course_id: 课程ID
            
        Returns:
            是否删除成功
        """
        try:
            course_dir = self.get_course_dir(course_id)
            if course_dir.exists():
                shutil.rmtree(course_dir)
            return True
        except Exception as e:
            print(f"Error deleting course: {e}")
            return False
    
    def get_file_path(self, course_id: str, relative_path: str) -> Path:
        """
        根据相对路径获取文件的完整路径
        
        Args:
            course_id: 课程ID
            relative_path: 相对于课程目录的相对路径
            
        Returns:
            文件的Path对象
        """
        return self.get_course_dir(course_id) / relative_path
    
    def file_exists(self, course_id: str, relative_path: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            course_id: 课程ID
            relative_path: 相对于课程目录的相对路径
            
        Returns:
            文件是否存在
        """
        return self.get_file_path(course_id, relative_path).exists()


# 全局实例
storage_manager = CourseStorageManager()

