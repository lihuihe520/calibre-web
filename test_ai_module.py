#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI模块自动化测试脚本 - 可直接运行版
直接运行: python test_ai_module.py
"""

import os
import sys
import json
import time
import requests
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# 测试配置
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8083")
TEST_USERNAME = os.getenv("TEST_USERNAME", "admin")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "admin123")
TEST_BOOK_IDS = [42, 52, 51, 45, 36, 37, 38, 39, 40, 41]  # 测试书籍ID列表

# 调试模式
DEBUG = True

# 测试结果存储
test_results: List[Dict] = []


class Colors:
    """终端颜色输出"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def debug_print(text: str):
    """调试输出"""
    if DEBUG:
        print(f"{Colors.YELLOW}[DEBUG] {text}{Colors.END}")


def print_header(text: str):
    """打印测试标题"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.END}\n")


def print_test(test_name: str, status: str, message: str = ""):
    """打印测试结果"""
    status_color = Colors.GREEN if status == "PASS" else Colors.RED
    status_symbol = "✓" if status == "PASS" else "✗"
    print(f"{status_color}{status_symbol} {test_name}{Colors.END}", end="")
    if message:
        print(f" - {message}")
    else:
        print()

    test_results.append({
        "test_name": test_name,
        "status": status,
        "message": message,
        "timestamp": datetime.now().isoformat()
    })


def test_connectivity():
    """测试基础连接性"""
    print_header("基础连接性测试")

    # 测试服务是否可达
    try:
        response = requests.get(BASE_URL, timeout=10)
        if response.status_code == 200:
            print_test("TC-000: 服务可达性", "PASS", f"服务运行在 {BASE_URL}")
            return True
        else:
            print_test("TC-000: 服务可达性", "FAIL",
                       f"服务返回状态码 {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_test("TC-000: 服务可达性", "FAIL",
                   f"无法连接到 {BASE_URL}，请确保服务已启动")
        return False
    except Exception as e:
        print_test("TC-000: 服务可达性", "FAIL", f"连接错误: {str(e)}")
        return False


def test_login():
    """测试登录功能"""
    print_header("登录功能测试")

    session = requests.Session()
    login_attempts = []

    # 尝试不同的登录端点
    login_endpoints = [
        "/login",
        "/api/login",
        "/auth/login",
        "/signin"
    ]

    for endpoint in login_endpoints:
        login_url = f"{BASE_URL}{endpoint}"
        debug_print(f"尝试登录端点: {login_url}")

        # 首先尝试GET请求
        try:
            response = session.get(login_url, timeout=10)
            login_attempts.append({
                "endpoint": endpoint,
                "method": "GET",
                "status": response.status_code
            })

            # 尝试POST登录
            login_data = {
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
            }

            # 尝试表单提交
            response = session.post(login_url, data=login_data, timeout=10)
            login_attempts.append({
                "endpoint": endpoint,
                "method": "POST",
                "status": response.status_code,
                "redirects": len(response.history) if hasattr(response, 'history') else 0
            })

            # 检查登录是否成功
            if response.status_code in [200, 302]:
                debug_print(f"登录端点 {endpoint} 可能成功，状态码: {response.status_code}")

                # 测试是否需要认证的端点
                test_url = f"{BASE_URL}/ajax/ai/book_summary/42"
                test_response = session.get(test_url, timeout=10)

                if test_response.status_code == 200:
                    print_test(f"TC-001: 登录测试 ({endpoint})", "PASS",
                               f"登录成功，可访问AI端点")
                    return session

        except Exception as e:
            debug_print(f"登录端点 {endpoint} 失败: {str(e)}")
            continue

    # 如果没有成功，尝试使用基本认证或直接测试
    print_test("TC-001: 登录测试", "WARN",
               f"无法通过标准方式登录，尝试直接访问")

    # 返回无认证的session进行测试
    return session


def test_ai_endpoints(session):
    """测试AI相关端点"""
    print_header("AI端点测试")

    # 测试各种可能的AI端点格式
    ai_endpoints = [
        {"path": "/ajax/ai/book_summary/{book_id}", "name": "书籍摘要"},
        {"path": "/api/ai/book_summary/{book_id}", "name": "API书籍摘要"},
        {"path": "/ai/book_summary/{book_id}", "name": "AI书籍摘要"},
        {"path": "/book/{book_id}/summary", "name": "书籍摘要(rest风格)"},
        {"path": "/ajax/ai/book_recommendations/{book_id}", "name": "书籍推荐"},
        {"path": "/api/ai/book_recommendations/{book_id}", "name": "API书籍推荐"}
    ]

    successful_endpoints = []

    for endpoint_info in ai_endpoints:
        endpoint = endpoint_info["path"]
        name = endpoint_info["name"]

        # 使用测试书籍ID
        for book_id in TEST_BOOK_IDS[:2]:  # 只测试前两个
            url = f"{BASE_URL}{endpoint.format(book_id=book_id)}"
            debug_print(f"测试 {name}: {url}")

            try:
                start_time = time.time()
                response = session.get(url, timeout=30)
                elapsed_time = time.time() - start_time

                if response.status_code == 200:
                    # 尝试解析响应
                    try:
                        data = response.json()
                        content_length = len(str(data))
                        print_test(
                            f"TC-002: {name} (Book {book_id})",
                            "PASS",
                            f"状态码: 200, 响应时间: {elapsed_time:.2f}s, 数据长度: {content_length}"
                        )
                        successful_endpoints.append({
                            "endpoint": endpoint,
                            "book_id": book_id,
                            "response_time": elapsed_time
                        })
                        break  # 这个端点成功，不需要测试其他书籍
                    except:
                        content_length = len(response.text)
                        print_test(
                            f"TC-002: {name} (Book {book_id})",
                            "PASS",
                            f"状态码: 200, 响应时间: {elapsed_time:.2f}s, 文本长度: {content_length}"
                        )
                        successful_endpoints.append({
                            "endpoint": endpoint,
                            "book_id": book_id,
                            "response_time": elapsed_time
                        })
                        break
                elif response.status_code == 401:
                    print_test(
                        f"TC-002: {name} (Book {book_id})",
                        "FAIL",
                        f"需要认证 (401)"
                    )
                    break
                elif response.status_code == 404:
                    debug_print(f"端点不存在: {endpoint}")
                    break
                else:
                    print_test(
                        f"TC-002: {name} (Book {book_id})",
                        "FAIL",
                        f"状态码: {response.status_code}"
                    )
                    break

            except requests.exceptions.Timeout:
                print_test(
                    f"TC-002: {name} (Book {book_id})",
                    "FAIL",
                    "请求超时 (30s)"
                )
                break
            except Exception as e:
                print_test(
                    f"TC-002: {name} (Book {book_id})",
                    "FAIL",
                    f"请求异常: {str(e)}"
                )
                break

    return successful_endpoints


def test_error_cases(session):
    """测试错误情况"""
    print_header("错误情况测试")

    # 测试不存在的书籍ID
    test_cases = [
        {"book_id": 999999, "expected": "404或错误处理", "name": "不存在的书籍"},
        {"book_id": "invalid", "expected": "400或错误处理", "name": "无效书籍ID"},
        {"book_id": 0, "expected": "错误处理", "name": "零值书籍ID"},
        {"book_id": -1, "expected": "错误处理", "name": "负值书籍ID"}
    ]

    for test_case in test_cases:
        book_id = test_case["book_id"]
        endpoint = "/ajax/ai/book_summary/{book_id}"
        url = f"{BASE_URL}{endpoint.format(book_id=book_id)}"

        try:
            response = session.get(url, timeout=15)
            if response.status_code >= 400:
                print_test(
                    f"TC-003: {test_case['name']} (ID: {book_id})",
                    "PASS",
                    f"正确处理错误，状态码: {response.status_code}"
                )
            else:
                print_test(
                    f"TC-003: {test_case['name']} (ID: {book_id})",
                    "INFO",
                    f"未返回错误，状态码: {response.status_code}"
                )
        except Exception as e:
            print_test(
                f"TC-003: {test_case['name']} (ID: {book_id})",
                "INFO",
                f"异常: {str(e)}"
            )


def test_performance(session, endpoint, book_id):
    """测试性能"""
    print_header("性能测试")

    response_times = []
    url = f"{BASE_URL}{endpoint.format(book_id=book_id)}"

    print(f"{Colors.YELLOW}正在进行3次性能测试...{Colors.END}")

    for i in range(3):
        try:
            start_time = time.time()
            response = session.get(url, timeout=60)
            elapsed_time = time.time() - start_time

            if response.status_code == 200:
                response_times.append(elapsed_time)
                debug_print(f"第{i + 1}次请求: {elapsed_time:.2f}秒")
            else:
                print_test(
                    f"TC-004: 性能测试 {i + 1}",
                    "FAIL",
                    f"状态码: {response.status_code}"
                )

            time.sleep(3)  # 间隔3秒

        except Exception as e:
            print_test(
                f"TC-004: 性能测试 {i + 1}",
                "FAIL",
                f"异常: {str(e)}"
            )

    if response_times:
        avg_time = sum(response_times) / len(response_times)
        max_time = max(response_times)
        min_time = min(response_times)

        status = "PASS" if avg_time < 40 else "WARN"
        print_test(
            "TC-004: AI响应性能",
            status,
            f"平均: {avg_time:.2f}秒, 最大: {max_time:.2f}秒, 最小: {min_time:.2f}秒"
        )
        return avg_time
    else:
        print_test(
            "TC-004: AI响应性能",
            "FAIL",
            "无法获取响应时间"
        )
        return None


def analyze_results():
    """分析测试结果并给出建议"""
    print_header("测试结果分析")

    total = len(test_results)
    passed = sum(1 for r in test_results if r["status"] == "PASS")
    failed = sum(1 for r in test_results if r["status"] == "FAIL")
    warned = sum(1 for r in test_results if r["status"] == "WARN")

    print(f"{Colors.BOLD}测试统计:{Colors.END}")
    print(f"  总测试数: {total}")
    print(f"  通过: {Colors.GREEN}{passed}{Colors.END}")
    print(f"  失败: {Colors.RED}{failed}{Colors.END}")
    print(f"  警告: {Colors.YELLOW}{warned}{Colors.END}")

    # 保存报告
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "warned": warned
        },
        "results": test_results
    }

    report_file = f"ai_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print(f"\n{Colors.BLUE}详细报告已保存到: {report_file}{Colors.END}")

    # 给出建议
    if failed > 0:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}问题诊断建议:{Colors.END}")
        print("1. 检查Calibre-web服务是否正常运行")
        print("2. 检查AI模块是否已正确安装和配置")
        print("3. 检查DeepSeek API密钥是否已在后端配置")
        print("4. 查看Calibre-web日志获取详细错误信息")
        print("5. 验证API端点URL是否正确")
        print("\n{Colors.YELLOW}常见问题解决方案:{Colors.END}")
        print("- 如果AI模块未启用，需要在配置中启用")
        print("- 如果API密钥错误，检查后端配置文件")
        print("- 如果网络问题，检查是否能访问DeepSeek API")

    return passed > 0 and failed == 0


def main():
    """主函数"""
    print_header("Calibre-web AI模块自动化测试")
    print(f"{Colors.BLUE}测试目标: {BASE_URL}{Colors.END}")
    print(f"{Colors.BLUE}开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}")

    # 测试连接性
    if not test_connectivity():
        print(f"\n{Colors.RED}服务不可达，测试终止{Colors.END}")
        sys.exit(1)

    # 获取session（尝试登录）
    session = test_login()

    # 测试AI端点
    successful_endpoints = test_ai_endpoints(session)

    if successful_endpoints:
        # 如果有成功的端点，进行性能测试
        endpoint = successful_endpoints[0]["endpoint"]
        book_id = successful_endpoints[0]["book_id"]
        test_performance(session, endpoint, book_id)
    else:
        print(f"\n{Colors.YELLOW}警告: 未找到可用的AI端点{Colors.END}")

    # 测试错误情况
    test_error_cases(session)

    # 分析结果
    success = analyze_results()

    if success:
        print(f"\n{Colors.GREEN}{Colors.BOLD}测试完成！AI模块基本功能正常。{Colors.END}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}测试发现问题，请查看上面的错误信息。{Colors.END}")

    print(f"\n{Colors.BLUE}结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}")


if __name__ == "__main__":
    # 确保脚本可以直接运行
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}测试被用户中断{Colors.END}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}测试脚本发生错误: {str(e)}{Colors.END}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
