import os
import sys
import subprocess
import logging
from pathlib import Path
import time

# =================配置区域=================
# dcm2niix 可执行文件的绝对路径
DCM2NIIX_EXE = r"E:\dcm2niix_win\dcm2niix.exe"

# 原始数据根目录 (DICOM/DOCM 数据)
INPUT_ROOT = r"E:\MedicalData_Uncompressed"

# 输出数据根目录 (脚本将自动创建此目录)
# 建议将输出与输入分开，避免文件混淆
OUTPUT_ROOT = r"E:\MedicalData_Cleaned_NIfTI"

# 日志文件路径
LOG_FILE = r"E:\conversion_log.txt"

# 转换参数设置
# -f: 输出文件名格式 (%i=患者ID, %n=患者名, %p=协议名, %t=时间, %s=序列号)
# -z: 压缩方式 (y=gz, n=无, i=内置gz)
# -b: 生成 BIDS JSON (y=是, n=否)
# -v: 详细输出 (n=普通, y=详细)
DCM_ARGS = ["-f", "%i_%p_%t_%s", "-z", "y", "-b", "y", "-v", "n"]
# =========================================

# 配置日志系统
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'  # 确保中文系统下日志编码正确
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)


def check_environment():
    """检查路径和工具是否就绪"""
    if not os.path.exists(DCM2NIIX_EXE):
        logging.critical(f"错误：找不到 dcm2niix 工具，路径为：{DCM2NIIX_EXE}")
        sys.exit(1)
    if not os.path.exists(INPUT_ROOT):
        logging.critical(f"错误：找不到输入目录，路径为：{INPUT_ROOT}")
        sys.exit(1)

    # 创建输出目录
    Path(OUTPUT_ROOT).mkdir(parents=True, exist_ok=True)
    logging.info("环境检查通过，准备开始转换任务...")


def is_dicom_folder(folder_path):
    """
    判断文件夹是否包含 DICOM 数据。
    不仅检查扩展名，还尝试读取文件头以验证 'DICM' 签名。
    这能解决.docm 扩展名错误标记的问题。
    """
    try:
        # 获取文件夹内前 5 个文件进行抽样检查
        files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

        for f in files[:5]:  # 只检查前5个文件以提高效率
            full_path = os.path.join(folder_path, f)

            # 策略1：检查扩展名 (包含用户提到的 docm)
            if f.lower().endswith(('.dcm', '.docm', '.ima')):
                return True

            # 策略2：检查文件头 (Magic Number)
            try:
                with open(full_path, 'rb') as file_obj:
                    file_obj.seek(128)
                    header = file_obj.read(4)
                    if header == b'DICM':
                        return True
            except:
                continue  # 如果读取失败，尝试下一个文件

    except Exception as e:
        logging.warning(f"无法扫描文件夹 {folder_path}: {e}")

    return False


def convert_directory(source_dir, target_base):
    """
    对单个包含 DICOM 的文件夹执行转换
    """
    # 计算相对路径，以便在输出目录中重建相同的层级结构
    rel_path = os.path.relpath(source_dir, INPUT_ROOT)
    output_dir = os.path.join(target_base, rel_path)

    # 如果输出子目录不存在，创建它
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 构建命令
    # dcm2niix 最后一个参数必须是输入目录
    # 修正说明：将可执行文件作为列表的第一个元素，与参数列表和输出参数拼接
    # 确保命令格式为: ['path/to/exe', '-arg1', 'val1',... , 'input_dir']
    cmd = [DCM2NIIX_EXE] + DCM_ARGS + ["-o", output_dir, source_dir]

    logging.info(f"正在处理: {source_dir}")
    logging.info(f"输出目标: {output_dir}")

    try:
        # 调用子进程执行转换
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',  # 防止 Windows 中文乱码
            errors='ignore'
        )

        if result.returncode == 0:
            logging.info(f"转换成功: {source_dir}")
            # 记录生成的 NIfTI 文件数量
            # dcm2niix 的标准输出包含转换细节
            for line in result.stdout.split('\n'):
                if "Convert" in line:
                    logging.info(f"  -> {line.strip()}")
        else:
            # dcm2niix 在找不到文件时也会返回非0，或者有其他警告
            logging.warning(f"转换可能存在问题 (代码 {result.returncode}): {source_dir}")
            logging.warning(f"工具输出: {result.stdout}")
            if result.stderr:
                logging.error(f"错误信息: {result.stderr}")

    except Exception as e:
        logging.error(f"执行转换命令时发生异常: {e}")


def main():
    check_environment()

    start_time = time.time()
    processed_count = 0

    logging.info(f"开始遍历目录树: {INPUT_ROOT}")

    # 使用 os.walk 递归遍历
    for root, dirs, files in os.walk(INPUT_ROOT):
        # 忽略已经存在的输出目录（如果用户错误地将输出设在输入目录内）
        if OUTPUT_ROOT in root:
            continue

        if not files:
            continue

        # 检查当前文件夹是否包含 DICOM 候选文件
        if is_dicom_folder(root):
            convert_directory(root, OUTPUT_ROOT)
            processed_count += 1

    elapsed = time.time() - start_time
    logging.info(f"批处理完成。共处理文件夹: {processed_count} 个。")
    logging.info(f"总耗时: {elapsed:.2f} 秒。")
    logging.info(f"请检查输出目录: {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()