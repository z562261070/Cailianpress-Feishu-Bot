#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON修复工具
用于修复财联社数据JSON文件中的格式错误
"""

import json
import re
import os
from typing import Dict, Any, List

class JSONFixer:
    def __init__(self):
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        
    def clean_text(self, text: str) -> str:
        """清理文本中的特殊字符"""
        if not isinstance(text, str):
            return text
            
        # 替换各种换行符和制表符
        text = text.replace('\r\n', ' ')  # Windows换行符
        text = text.replace('\r', ' ')    # Mac换行符
        text = text.replace('\n', ' ')    # Unix换行符
        text = text.replace('\t', ' ')    # 制表符
        
        # 替换其他控制字符
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', text)
        
        # 处理引号
        text = text.replace('"', '\\"')   # 转义双引号
        text = text.replace("'", "\\'")   # 转义单引号
        
        # 合并多个空格
        text = re.sub(r'\s+', ' ', text)
        
        # 去除首尾空格
        text = text.strip()
        
        return text
    
    def clean_data_recursive(self, data: Any) -> Any:
        """递归清理数据结构中的所有文本"""
        if isinstance(data, dict):
            return {key: self.clean_data_recursive(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.clean_data_recursive(item) for item in data]
        elif isinstance(data, str):
            return self.clean_text(data)
        else:
            return data
    
    def fix_json_file(self, file_path: str) -> bool:
        """修复JSON文件"""
        try:
            print(f"正在修复文件: {file_path}")
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                print(f"文件不存在: {file_path}")
                return False
            
            # 读取原始文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_content = f.read()
            
            print(f"原始文件大小: {len(raw_content)} 字符")
            
            # 尝试解析JSON
            try:
                data = json.loads(raw_content)
                print("JSON格式正确，无需修复")
                return True
            except json.JSONDecodeError as e:
                print(f"JSON解析错误: {e}")
                print(f"错误位置: {e.pos}")
                
                # 显示错误位置附近的内容
                start = max(0, e.pos - 50)
                end = min(len(raw_content), e.pos + 50)
                error_context = raw_content[start:end]
                print(f"错误位置附近的内容: {repr(error_context)}")
            
            # 尝试修复JSON
            print("尝试修复JSON...")
            
            # 方法1: 逐行清理
            lines = raw_content.split('\n')
            cleaned_lines = []
            
            for line in lines:
                # 清理每一行
                cleaned_line = self.clean_text(line)
                if cleaned_line:  # 只保留非空行
                    cleaned_lines.append(cleaned_line)
            
            cleaned_content = '\n'.join(cleaned_lines)
            
            # 尝试解析清理后的内容
            try:
                data = json.loads(cleaned_content)
                print("方法1成功: 逐行清理")
            except json.JSONDecodeError:
                print("方法1失败，尝试方法2...")
                
                # 方法2: 更激进的清理
                # 移除所有控制字符
                cleaned_content = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', raw_content)
                # 修复常见的JSON错误
                cleaned_content = re.sub(r',\s*}', '}', cleaned_content)  # 移除多余的逗号
                cleaned_content = re.sub(r',\s*]', ']', cleaned_content)  # 移除多余的逗号
                
                try:
                    data = json.loads(cleaned_content)
                    print("方法2成功: 激进清理")
                except json.JSONDecodeError as e:
                    print(f"方法2也失败了: {e}")
                    return False
            
            # 递归清理数据结构
            print("递归清理数据结构...")
            cleaned_data = self.clean_data_recursive(data)
            
            # 创建备份
            backup_path = file_path + '.backup'
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(raw_content)
            print(f"原始文件已备份到: {backup_path}")
            
            # 保存修复后的文件
            with open(file_path, 'w', encoding='utf-8', newline='') as f:
                json.dump(cleaned_data, f, ensure_ascii=False, indent=2, separators=(',', ': '))
            
            print(f"文件修复完成: {file_path}")
            
            # 验证修复后的文件
            with open(file_path, 'r', encoding='utf-8') as f:
                test_content = f.read()
            
            try:
                json.loads(test_content)
                print("修复后的文件JSON格式验证通过")
                return True
            except json.JSONDecodeError as e:
                print(f"修复后的文件仍有错误: {e}")
                return False
                
        except Exception as e:
            print(f"修复过程中发生错误: {e}")
            return False
    
    def fix_all_json_files(self):
        """修复所有JSON文件"""
        json_files = [
            'cailianpress_data.json',
            'cailianpress_summary.json'
        ]
        
        success_count = 0
        for filename in json_files:
            file_path = os.path.join(self.base_path, filename)
            if self.fix_json_file(file_path):
                success_count += 1
        
        print(f"\n修复完成: {success_count}/{len(json_files)} 个文件修复成功")

def main():
    """主函数"""
    fixer = JSONFixer()
    fixer.fix_all_json_files()

if __name__ == "__main__":
    main()
