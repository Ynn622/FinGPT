from functools import wraps
import inspect

def log_print(func):
    if inspect.iscoroutinefunction(func):  # 如果是 async function
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            func_name = func.__name__
            try:
                arg_str = f"{', '.join(map(str, args))}" if args else ""
                kwarg_str = f", kwargs={kwargs}" if kwargs else ""
                print(f"🟣 [FunctionCall] {func_name}({arg_str}{kwarg_str})")
                return await func(*args, **kwargs)
            except Exception as e:
                main_arg = args[0] if args else None
                print(f"🔴 [Error] {func_name}({main_arg}): {str(e)}")
                raise
        return async_wrapper
    else:  # 如果是普通 def
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            func_name = func.__name__
            try:
                arg_str = f"{', '.join(map(str, args))}" if args else ""
                kwarg_str = f", kwargs={kwargs}" if kwargs else ""
                print(f"🟣 [FunctionCall] {func_name}({arg_str}{kwarg_str})")
                return func(*args, **kwargs)
            except Exception as e:
                main_arg = args[0] if args else None
                print(f"🔴 [Error] {func_name}({main_arg}): {str(e)}")
                raise
        return sync_wrapper