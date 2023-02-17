def check_syntax(port: str):
    print("start")
    try:
      print("inside try")
      int(port)
    except ValueError:
      return False
    print("after everything")
    return True

print(check_syntax(10))
print(check_syntax(""))

int("")