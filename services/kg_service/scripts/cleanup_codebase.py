"""
Cleanup Script for kg_service

Identifies and helps remove unused files before GitHub commit.
Run this to prepare your codebase for production.
"""

import os
from pathlib import Path
from typing import List, Set

# Base directory
BASE_DIR = Path(__file__).parent.parent


def get_unused_test_scripts() -> List[Path]:
    """Identify unused exploration/test scripts."""
    research_dir = BASE_DIR / "scripts" / "research"
    
    # Keep these (production-ready tests)
    keep_files = {
        'test_heterogeneous_gnn.py',
        'test_cross_type_predictions.py',
        'comprehensive_graph_analysis.py',
        '__init__.py'
    }
    
    # Find all Python files
    all_files = list(research_dir.glob("*.py"))
    
    # Return files not in keep list
    unused = [f for f in all_files if f.name not in keep_files]
    
    return unused


def get_redundant_service_files() -> List[Path]:
    """Identify potentially redundant service files."""
    services_dir = BASE_DIR / "src" / "services"
    
    # These might be redundant if not used
    check_files = [
        services_dir / "embeddings.py",  # Old embedding service (if using gnn_embeddings)
        # Add more as needed
    ]
    
    return [f for f in check_files if f.exists()]


def check_file_usage(file_path: Path) -> Set[Path]:
    """Check which files import this module."""
    module_name = file_path.stem
    import_patterns = [
        f"from {module_name} import",
        f"import {module_name}",
        f"from services.{module_name} import",
        f"from ..{module_name} import"
    ]
    
    # Search in src and tests
    search_dirs = [
        BASE_DIR / "src",
        BASE_DIR / "tests"
    ]
    
    importers = set()
    
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
            
        for py_file in search_dir.rglob("*.py"):
            if py_file == file_path:
                continue
                
            try:
                content = py_file.read_text(encoding='utf-8')
                if any(pattern in content for pattern in import_patterns):
                    importers.add(py_file)
            except Exception:
                pass
    
    return importers


def analyze_codebase():
    """Analyze codebase for cleanup opportunities."""
    print("=" * 80)
    print("KG_SERVICE CODEBASE CLEANUP ANALYSIS")
    print("=" * 80)
    
    # 1. Unused test scripts
    print("\n1. Unused Research Scripts (safe to remove):")
    print("-" * 80)
    unused_scripts = get_unused_test_scripts()
    
    if unused_scripts:
        for script in unused_scripts:
            print(f"   📄 {script.relative_to(BASE_DIR)}")
            importers = check_file_usage(script)
            if importers:
                print(f"      ⚠️  Used by {len(importers)} file(s)")
            else:
                print(f"      ✅ Not imported anywhere - safe to remove")
    else:
        print("   ✅ No unused scripts found")
    
    # 2. Potentially redundant services
    print("\n2. Potentially Redundant Service Files:")
    print("-" * 80)
    redundant = get_redundant_service_files()
    
    if redundant:
        for service in redundant:
            print(f"   📄 {service.relative_to(BASE_DIR)}")
            importers = check_file_usage(service)
            if importers:
                print(f"      ⚠️  Used by {len(importers)} file(s):")
                for importer in list(importers)[:3]:  # Show first 3
                    print(f"         - {importer.relative_to(BASE_DIR)}")
                if len(importers) > 3:
                    print(f"         ... and {len(importers) - 3} more")
            else:
                print(f"      ✅ Not imported - candidate for removal")
    else:
        print("   ✅ No redundant files found")
    
    # 3. Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    total_removable = len([s for s in unused_scripts if not check_file_usage(s)])
    
    if total_removable > 0:
        print(f"\n✅ {total_removable} file(s) safe to remove")
        print("\nTo remove, run:")
        print(f"   python {Path(__file__).name} --remove")
    else:
        print("\n✅ Codebase is clean! Ready for GitHub commit.")
    
    print("\n📋 Files to keep (production-ready):")
    print("   ✅ src/services/gnn_embeddings.py       - Core GNN implementation")
    print("   ✅ src/services/config/gnn_config.py    - Configuration")
    print("   ✅ src/api/research.py                  - GNN API endpoints")
    print("   ✅ scripts/research/test_heterogeneous_gnn.py")
    print("   ✅ scripts/research/test_cross_type_predictions.py")
    print("   ✅ scripts/research/comprehensive_graph_analysis.py")
    print("   ✅ docs/GNN_MODULE_README.md")
    print("   ✅ docs/HETEROGENEOUS_GNN_STEP_BY_STEP.md")
    print("   ✅ docs/HETEROGENEOUS_GNN_UPGRADE.md")


def remove_unused_files():
    """Actually remove unused files (use with caution)."""
    print("=" * 80)
    print("REMOVING UNUSED FILES")
    print("=" * 80)
    
    unused_scripts = get_unused_test_scripts()
    removed_count = 0
    
    for script in unused_scripts:
        importers = check_file_usage(script)
        if not importers:
            print(f"Removing: {script.relative_to(BASE_DIR)}")
            # Uncomment to actually remove:
            # script.unlink()
            removed_count += 1
        else:
            print(f"Skipping: {script.relative_to(BASE_DIR)} (still in use)")
    
    print(f"\n✅ Would remove {removed_count} file(s)")
    print("⚠️  Uncomment script.unlink() to actually delete files")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--remove":
        remove_unused_files()
    else:
        analyze_codebase()
        print("\n" + "=" * 80)
        print("💡 TIP: Review the analysis above before committing to GitHub")
        print("=" * 80)
