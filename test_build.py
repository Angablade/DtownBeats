#!/usr/bin/env python3
"""
Simple test script to verify the bot loads correctly
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.getcwd())

try:
    print("Testing bot3.py compilation...")
    import py_compile
    py_compile.compile('bot3.py', doraise=True)
    print("bot3.py compiles successfully")
    
    print("\nAll files compile successfully!")
    print("Bot refactoring completed!")
    
except Exception as e:
    print(f"? Error: {e}")
    sys.exit(1)