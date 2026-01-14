#!/usr/bin/env python3

"""
Project Verification Script
Checks that all required files are present and properly configured
"""

import os
import sys
from pathlib import Path

def check_file(path, description):
    """Check if a file exists"""
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"✓ {description}: {path} ({size} bytes)")
        return True
    else:
        print(f"✗ MISSING: {description}: {path}")
        return False

def check_directory(path, description):
    """Check if a directory exists"""
    if os.path.isdir(path):
        count = len(os.listdir(path))
        print(f"✓ {description}: {path} ({count} items)")
        return True
    else:
        print(f"✗ MISSING: {description}: {path}")
        return False

def main():
    """Main verification"""
    print("=" * 60)
    print("Streaming Observability Platform - File Verification")
    print("=" * 60)
    print()
    
    checks = []
    
    # Root files
    print("📄 Root Configuration Files:")
    checks.append(check_file("docker-compose.yml", "Podman Compose config"))
    checks.append(check_file("requirements.txt", "Python requirements"))
    checks.append(check_file(".env.example", "Environment template"))
    checks.append(check_file(".gitignore", "Git ignore rules"))
    checks.append(check_file("Makefile", "Make commands"))
    print()
    
    # Documentation
    print("📚 Documentation:")
    checks.append(check_file("README.md", "Main README"))
    checks.append(check_file("DESIGN.md", "System design doc"))
    checks.append(check_file("QUICKSTART.md", "Quick start guide"))
    checks.append(check_file("PROJECT_SUMMARY.md", "Project summary"))
    checks.append(check_file("LICENSE", "License file"))
    print()
    
    # Event Generator
    print("🎲 Event Generator:")
    checks.append(check_directory("event_generator", "Event generator dir"))
    checks.append(check_file("event_generator/generator.py", "Generator script"))
    checks.append(check_file("event_generator/Dockerfile", "Generator Dockerfile"))
    print()
    
    # Spark
    print("⚡ Spark Streaming:")
    checks.append(check_directory("spark", "Spark dir"))
    checks.append(check_file("spark/streaming_job.py", "Streaming job"))
    print()
    
    # Anomaly Detection
    print("🚨 Anomaly Detection:")
    checks.append(check_directory("anomaly_detection", "Anomaly detection dir"))
    checks.append(check_file("anomaly_detection/detector.py", "Detector script"))
    checks.append(check_file("anomaly_detection/Dockerfile", "Detector Dockerfile"))
    print()
    
    # LLM Narrator
    print("🤖 LLM Narrator:")
    checks.append(check_directory("llm", "LLM dir"))
    checks.append(check_file("llm/narrator.py", "Narrator script"))
    checks.append(check_file("llm/Dockerfile", "Narrator Dockerfile"))
    print()
    
    # Airflow
    print("🔄 Airflow:")
    checks.append(check_directory("airflow", "Airflow dir"))
    checks.append(check_directory("airflow/dags", "Airflow DAGs dir"))
    checks.append(check_file("airflow/Dockerfile", "Airflow Dockerfile"))
    checks.append(check_file("airflow/requirements-airflow.txt", "Airflow requirements"))
    checks.append(check_file("airflow/dags/monitoring_dag.py", "Monitoring DAG"))
    checks.append(check_file("airflow/dags/data_quality_dag.py", "Data quality DAG"))
    print()
    
    # Dashboard
    print("📊 Dashboard:")
    checks.append(check_directory("dashboard", "Dashboard dir"))
    checks.append(check_file("dashboard/app.py", "Dashboard app"))
    checks.append(check_file("dashboard/Dockerfile", "Dashboard Dockerfile"))
    print()
    
    # Scripts
    print("🔧 Scripts:")
    checks.append(check_directory("scripts", "Scripts dir"))
    checks.append(check_file("scripts/init.sh", "Init script"))
    checks.append(check_file("scripts/init_db.py", "DB init script"))
    checks.append(check_file("scripts/health_check.sh", "Health check script"))
    checks.append(check_file("scripts/shutdown.sh", "Shutdown script"))
    print()
    
    # Data directory
    print("💾 Data Directory:")
    checks.append(check_directory("data", "Data directory"))
    print()
    
    # Summary
    print("=" * 60)
    passed = sum(checks)
    total = len(checks)
    
    if passed == total:
        print(f"✅ ALL CHECKS PASSED: {passed}/{total}")
        print()
        print("🎉 Project is complete and ready to run!")
        print()
        print("Next steps:")
        print("  1. Run: make init")
        print("  2. Run: make start")
        print("  3. Open: http://localhost:8501")
        print()
        return 0
    else:
        print(f"❌ SOME CHECKS FAILED: {passed}/{total}")
        print()
        print("Please fix missing files before proceeding.")
        print()
        return 1

if __name__ == '__main__':
    sys.exit(main())
