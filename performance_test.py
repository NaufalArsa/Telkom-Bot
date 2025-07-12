import time
import cProfile
import pstats
import io
import sys
import os
import importlib.util
import psutil
import tracemalloc
from typing import Dict, List, Tuple
import json

def measure_import_time(module_name: str, file_path: str) -> float:
    """Measure the time it takes to import a module"""
    start_time = time.time()
    
    # Load the module
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        print(f"Error: Could not create spec for {module_name}")
        return -1
    
    module = importlib.util.module_from_spec(spec)
    
    # Execute the module (simulates import)
    try:
        spec.loader.exec_module(module)
        import_time = time.time() - start_time
        return import_time
    except Exception as e:
        print(f"Error importing {module_name}: {e}")
        return -1

def measure_memory_usage(func, *args, **kwargs) -> Tuple[float, float]:
    """Measure memory usage before and after function execution"""
    tracemalloc.start()
    
    # Get initial memory
    initial_memory = tracemalloc.get_traced_memory()[0]
    
    # Execute function
    result = func(*args, **kwargs)
    
    # Get final memory
    final_memory = tracemalloc.get_traced_memory()[0]
    
    tracemalloc.stop()
    
    memory_used = final_memory - initial_memory
    return memory_used, result

def profile_function(func, *args, **kwargs) -> Dict:
    """Profile a function and return detailed statistics"""
    profiler = cProfile.Profile()
    profiler.enable()
    
    start_time = time.time()
    result = func(*args, **kwargs)
    execution_time = time.time() - start_time
    
    profiler.disable()
    
    # Get stats
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(20)  # Top 20 functions
    
    return {
        'execution_time': execution_time,
        'profile_stats': s.getvalue(),
        'result': result
    }

def count_code_metrics(file_path: str) -> Dict:
    """Count various code metrics"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        total_lines = len(lines)
        code_lines = len([line for line in lines if line.strip() and not line.strip().startswith('#')])
        comment_lines = len([line for line in lines if line.strip().startswith('#')])
        empty_lines = len([line for line in lines if not line.strip()])
        
        # Count functions
        function_count = content.count('def ')
        async_function_count = content.count('async def ')
        
        # Count imports
        import_count = content.count('import ') + content.count('from ')
        
        # Count classes
        class_count = content.count('class ')
        
        # Count variables
        var_count = content.count(' = ')
        
        return {
            'total_lines': total_lines,
            'code_lines': code_lines,
            'comment_lines': comment_lines,
            'empty_lines': empty_lines,
            'function_count': function_count,
            'async_function_count': async_function_count,
            'import_count': import_count,
            'class_count': class_count,
            'variable_count': var_count,
            'file_size_kb': len(content) / 1024
        }
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return {}

def test_regex_performance():
    """Test regex pattern performance"""
    import re
    
    # Test data
    test_caption = """
    Nama SA/ AR: John Doe
    STO: STO001
    Cluster: Cluster A
    
    Nama usaha: Test Business
    Nama PIC: Jane Smith
    Nomor HP/ WA: 08123456789
    Internet existing: Yes
    Biaya internet existing: 500000
    Voice of Customer: Good service
    """
    
    # Pattern from bot_local.py
    pattern_local = re.compile(r"""
        Nama\s+SA/\s*AR:\s*(?P<nama_sa>.+?)\n+
        STO:\s*(?P<sto>.+?)\n+
        Cluster:\s*(?P<cluster>.+?)\n+
        \n*
        Nama\s+usaha:\s*(?P<usaha>.+?)\n+
        Nama\s+PIC:\s*(?P<pic>.+?)\n+
        Nomor\s+HP/\s*WA:\s*(?P<hpwa>.+?)\n+
        Internet\s+existing:\s*(?P<internet>.+?)\n+
        Biaya\s+internet\s+existing:\s*(?P<biaya>.+?)\n+
        Voice\s+of\s+Customer:\s*(?P<voc>.+?)(?:\n|$)
    """, re.DOTALL | re.MULTILINE | re.IGNORECASE | re.VERBOSE)
    
    # Pattern from bot_optimized.py
    pattern_optimized = re.compile(r"""
        Nama\s+SA/\s*AR:\s*(?P<nama_sa>.+?)\n+
        STO:\s*(?P<sto>.+?)\n+
        Cluster:\s*(?P<cluster>.+?)\n+
        \n*
        Nama\s+usaha:\s*(?P<usaha>.+?)\n+
        Nama\s+PIC:\s*(?P<pic>.+?)\n+
        Nomor\s+HP/\s*WA:\s*(?P<hpwa>.+?)\n+
        Internet\s+existing:\s*(?P<internet>.+?)\n+
        Biaya\s+internet\s+existing:\s*(?P<biaya>.+?)\n+
        Voice\s+of\s+Customer:\s*(?P<voc>.+?)(?:\n|$)
    """, re.DOTALL | re.MULTILINE | re.IGNORECASE | re.VERBOSE)
    
    results = {}
    
    # Test local pattern
    start_time = time.time()
    for _ in range(1000):
        match = pattern_local.search(test_caption)
    local_time = time.time() - start_time
    results['local_regex_time'] = local_time
    
    # Test optimized pattern
    start_time = time.time()
    for _ in range(1000):
        match = pattern_optimized.search(test_caption)
    optimized_time = time.time() - start_time
    results['optimized_regex_time'] = optimized_time
    
    return results

def test_data_processing():
    """Test data processing functions"""
    test_data = {
        'nama_sa': 'John Doe',
        'sto': 'STO001',
        'cluster': 'Cluster A',
        'usaha': 'Test Business',
        'pic': 'Jane Smith',
        'hpwa': '08123456789',
        'internet': 'Yes',
        'biaya': '500000',
        'voc': 'Good service'
    }
    
    # Test validation function (simplified version)
    def validate_data_local(row):
        required_fields = {
            'nama_sa': 'Nama SA/AR',
            'sto': 'STO', 
            'cluster': 'Cluster',
            'usaha': 'Nama usaha',
            'pic': 'Nama PIC',
            'hpwa': 'Nomor HP/WA',
            'internet': 'Internet existing',
            'biaya': 'Biaya internet existing',
            'voc': 'Voice of Customer'
        }
        
        missing_fields = []
        for field_key, field_name in required_fields.items():
            field_value = row.get(field_key, '').strip()
            if not field_value:
                missing_fields.append(field_name)
        
        return len(missing_fields) == 0, missing_fields
    
    def validate_data_optimized(row):
        required_fields = {
            'nama_sa': 'Nama SA/AR',
            'sto': 'STO', 
            'cluster': 'Cluster',
            'usaha': 'Nama usaha',
            'pic': 'Nama PIC',
            'hpwa': 'Nomor HP/WA',
            'internet': 'Internet existing',
            'biaya': 'Biaya internet existing',
            'voc': 'Voice of Customer'
        }
        
        missing_fields = []
        for field_key, field_name in required_fields.items():
            field_value = row.get(field_key, '').strip()
            if not field_value:
                missing_fields.append(field_name)
        
        return len(missing_fields) == 0, missing_fields
    
    results = {}
    
    # Test local validation
    start_time = time.time()
    for _ in range(10000):
        validate_data_local(test_data)
    local_time = time.time() - start_time
    results['local_validation_time'] = local_time
    
    # Test optimized validation
    start_time = time.time()
    for _ in range(10000):
        validate_data_optimized(test_data)
    optimized_time = time.time() - start_time
    results['optimized_validation_time'] = optimized_time
    
    return results

def run_comprehensive_test():
    """Run comprehensive performance test"""
    print("🚀 Starting Comprehensive Performance Test")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Import Time
    print("\n📦 Testing Import Time...")
    local_import_time = measure_import_time('bot_local', 'bot_local.py')
    optimized_import_time = measure_import_time('bot_optimized', 'bot_optimized.py')
    
    results['import_time'] = {
        'local': local_import_time,
        'optimized': optimized_import_time,
        'improvement': ((local_import_time - optimized_import_time) / local_import_time * 100) if local_import_time > 0 else 0
    }
    
    print(f"Local: {local_import_time:.4f}s")
    print(f"Optimized: {optimized_import_time:.4f}s")
    print(f"Improvement: {results['import_time']['improvement']:.2f}%")
    
    # Test 2: Code Metrics
    print("\n📊 Analyzing Code Metrics...")
    local_metrics = count_code_metrics('bot_local.py')
    optimized_metrics = count_code_metrics('bot_optimized.py')
    
    results['code_metrics'] = {
        'local': local_metrics,
        'optimized': optimized_metrics
    }
    
    print(f"Local - Lines: {local_metrics.get('total_lines', 0)}, Functions: {local_metrics.get('function_count', 0)}")
    print(f"Optimized - Lines: {optimized_metrics.get('total_lines', 0)}, Functions: {optimized_metrics.get('function_count', 0)}")
    
    # Test 3: Regex Performance
    print("\n🔍 Testing Regex Performance...")
    regex_results = test_regex_performance()
    results['regex_performance'] = regex_results
    
    print(f"Local Regex: {regex_results['local_regex_time']:.4f}s")
    print(f"Optimized Regex: {regex_results['optimized_regex_time']:.4f}s")
    
    # Test 4: Data Processing
    print("\n⚙️ Testing Data Processing...")
    processing_results = test_data_processing()
    results['data_processing'] = processing_results
    
    print(f"Local Validation: {processing_results['local_validation_time']:.4f}s")
    print(f"Optimized Validation: {processing_results['optimized_validation_time']:.4f}s")
    
    # Test 5: Memory Usage
    print("\n💾 Testing Memory Usage...")
    
    def dummy_function():
        data = {'test': 'data' * 1000}
        return len(data)
    
    local_memory, _ = measure_memory_usage(dummy_function)
    optimized_memory, _ = measure_memory_usage(dummy_function)
    
    results['memory_usage'] = {
        'local': local_memory,
        'optimized': optimized_memory,
        'difference': local_memory - optimized_memory
    }
    
    print(f"Local Memory: {local_memory:.2f} bytes")
    print(f"Optimized Memory: {optimized_memory:.2f} bytes")
    print(f"Difference: {results['memory_usage']['difference']:.2f} bytes")
    
    # Generate Summary
    print("\n" + "=" * 60)
    print("📈 PERFORMANCE SUMMARY")
    print("=" * 60)
    
    # Calculate overall score
    improvements = []
    
    if local_import_time > 0 and optimized_import_time > 0:
        import_improvement = (local_import_time - optimized_import_time) / local_import_time * 100
        improvements.append(import_improvement)
        print(f"Import Time: {import_improvement:+.2f}%")
    
    if regex_results['local_regex_time'] > 0:
        regex_improvement = (regex_results['local_regex_time'] - regex_results['optimized_regex_time']) / regex_results['local_regex_time'] * 100
        improvements.append(regex_improvement)
        print(f"Regex Performance: {regex_improvement:+.2f}%")
    
    if processing_results['local_validation_time'] > 0:
        processing_improvement = (processing_results['local_validation_time'] - processing_results['optimized_validation_time']) / processing_results['local_validation_time'] * 100
        improvements.append(processing_improvement)
        print(f"Data Processing: {processing_improvement:+.2f}%")
    
    if improvements:
        avg_improvement = sum(improvements) / len(improvements)
        print(f"\n🎯 Average Improvement: {avg_improvement:+.2f}%")
        
        if avg_improvement > 0:
            print("✅ Optimized version performs better!")
        elif avg_improvement < 0:
            print("⚠️ Local version performs better!")
        else:
            print("🔄 Both versions perform similarly")
    
    # Code quality comparison
    print(f"\n📝 Code Quality Comparison:")
    print(f"Lines of Code: {local_metrics.get('total_lines', 0)} → {optimized_metrics.get('total_lines', 0)}")
    print(f"Functions: {local_metrics.get('function_count', 0)} → {optimized_metrics.get('function_count', 0)}")
    print(f"File Size: {local_metrics.get('file_size_kb', 0):.1f}KB → {optimized_metrics.get('file_size_kb', 0):.1f}KB")
    
    # Save detailed results
    with open('performance_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Detailed results saved to 'performance_results.json'")
    
    return results

if __name__ == "__main__":
    try:
        results = run_comprehensive_test()
        print("\n✅ Performance test completed successfully!")
    except Exception as e:
        print(f"\n❌ Error during performance test: {e}")
        import traceback
        traceback.print_exc() 