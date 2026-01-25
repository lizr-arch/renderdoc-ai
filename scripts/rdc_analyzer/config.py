"""
Mali 分析器配置
==============

配置优先级:
1. 环境变量
2. 配置文件 (config.json)
3. 默认值
"""

import os
import json

# 默认配置
DEFAULT_CONFIG = {
    "malioc_path": r"D:\Program Files\Arm\Arm Performance Studio 2025.3\mali_offline_compiler\malioc.exe",
    "target_gpu": "Mali-G78",
    "output_dir": r"d:\Code\git\renderdoc\scripts\rdc_analyzer\output",
    "max_shaders": 50,
    "adreno_profiler_path": "",
    "adreno_target_gpu": "Adreno 740",
    
    # 支持的 GPU 列表 (运行 malioc --list 获取完整列表)
    "supported_gpus": [
        "Mali-G78",      # Valhall, 旗舰
        "Mali-G77",      # Valhall
        "Mali-G76",      # Bifrost
        "Mali-G72",      # Bifrost
        "Mali-G57",      # Valhall, 中端
        "Mali-G52",      # Bifrost, 中端
        "Mali-G31",      # Bifrost, 入门
        "Mali-G715",     # 5th Gen, 旗舰
        "Mali-G615",     # 5th Gen, 中端
        "Mali-G720",     # Arm Immortalis
    ]
}

def _get_config_path():
    """获取配置文件路径"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "config.json")

def load_config():
    """加载配置，优先级: 环境变量 > config.json > 默认值"""
    config = DEFAULT_CONFIG.copy()
    
    # 尝试从配置文件加载
    config_path = _get_config_path()
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception as e:
            print(f"[WARN] Failed to load config.json: {e}")
    
    # 环境变量覆盖
    if os.environ.get('MALIOC_PATH'):
        config['malioc_path'] = os.environ['MALIOC_PATH']
    if os.environ.get('MALI_TARGET_GPU'):
        config['target_gpu'] = os.environ['MALI_TARGET_GPU']
    if os.environ.get('MALI_OUTPUT_DIR'):
        config['output_dir'] = os.environ['MALI_OUTPUT_DIR']
    if os.environ.get('MALI_MAX_SHADERS'):
        try:
            config['max_shaders'] = int(os.environ['MALI_MAX_SHADERS'])
        except ValueError:
            pass
    if os.environ.get('ADRENO_PROFILER_PATH'):
        config['adreno_profiler_path'] = os.environ['ADRENO_PROFILER_PATH']
    if os.environ.get('ADRENO_TARGET_GPU'):
        config['adreno_target_gpu'] = os.environ['ADRENO_TARGET_GPU']
    
    return config

def save_config(config):
    """保存配置到文件"""
    config_path = _get_config_path()
    # 只保存非默认值
    save_data = {}
    for key, value in config.items():
        if key not in DEFAULT_CONFIG or value != DEFAULT_CONFIG[key]:
            save_data[key] = value
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save config: {e}")
        return False

def find_malioc():
    """自动检测 malioc 路径"""
    # 常见安装路径
    search_paths = [
        r"D:\Program Files\Arm\Arm Performance Studio 2025.3\mali_offline_compiler\malioc.exe",
        r"C:\Program Files\Arm\Arm Performance Studio 2025.3\mali_offline_compiler\malioc.exe",
        r"D:\Program Files\Arm Mobile Studio\mali_offline_compiler\malioc.exe",
        r"C:\Program Files\Arm Mobile Studio\mali_offline_compiler\malioc.exe",
    ]
    
    # 检查 PATH
    for path_dir in os.environ.get('PATH', '').split(os.pathsep):
        candidate = os.path.join(path_dir, 'malioc.exe')
        if os.path.exists(candidate):
            return candidate
    
    # 检查已知路径
    for path in search_paths:
        if os.path.exists(path):
            return path
    
    return None

def validate_config(config):
    """验证配置"""
    errors = []
    
    # 检查 malioc 路径
    if not os.path.exists(config.get('malioc_path', '')):
        # 尝试自动检测
        found = find_malioc()
        if found:
            config['malioc_path'] = found
            print(f"[INFO] Auto-detected malioc: {found}")
        else:
            errors.append(f"malioc not found: {config.get('malioc_path')}")
    
    # 检查输出目录
    output_dir = config.get('output_dir', '')
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"[INFO] Created output directory: {output_dir}")
        except Exception as e:
            errors.append(f"Cannot create output directory: {e}")
    
    # 检查 Adreno Profiler 路径（可选）
    adreno_profiler = config.get('adreno_profiler_path', '')
    if adreno_profiler and not os.path.exists(adreno_profiler):
        errors.append(f"Adreno profiler not found: {adreno_profiler}")
    
    return errors

# 全局配置实例
_config = None

def get_config():
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = load_config()
        errors = validate_config(_config)
        for err in errors:
            print(f"[WARN] Config issue: {err}")
    return _config

def set_target_gpu(gpu_name):
    """设置目标 GPU"""
    config = get_config()
    config['target_gpu'] = gpu_name
    print(f"[INFO] Target GPU set to: {gpu_name}")

def set_malioc_path(path):
    """设置 malioc 路径"""
    config = get_config()
    if os.path.exists(path):
        config['malioc_path'] = path
        print(f"[INFO] malioc path set to: {path}")
        return True
    else:
        print(f"[ERROR] Path does not exist: {path}")
        return False


if __name__ == "__main__":
    # 测试配置加载
    cfg = get_config()
    print("Current Configuration:")
    print(f"  malioc_path: {cfg['malioc_path']}")
    print(f"  target_gpu: {cfg['target_gpu']}")
    print(f"  output_dir: {cfg['output_dir']}")
    print(f"  max_shaders: {cfg['max_shaders']}")
