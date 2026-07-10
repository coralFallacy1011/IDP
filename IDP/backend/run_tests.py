import subprocess, sys
result = subprocess.run([sys.executable, "-m", "pytest", "tests/test_biometric_auth.py", "-v", "--tb=long", "--hypothesis-seed=0"], capture_output=True, text=True, cwd=".")
print(result.stdout)
print(result.stderr)
