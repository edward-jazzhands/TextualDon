
```
         import shutil
 
         try:
-            width, height = shutil.get_terminal_size()
+            width, height = os.get_terminal_size(self._file.fileno())
         except (AttributeError, ValueError, OSError):
             try:
-                width, height = shutil.get_terminal_size()
+                width, height = os.get_terminal_size(self._file.fileno())
             except (AttributeError, ValueError, OSError):
                 pass
         width = width or 80
```        

```
        import shutil

        try:
-            width, height = shutil.get_terminal_size()
+            width, height = os.get_terminal_size(self._file.fileno())
        except (AttributeError, ValueError, OSError):
            try:
-                width, height = shutil.get_terminal_size()
+                width, height = os.get_terminal_size(self._file.fileno())
            except (AttributeError, ValueError, OSError):
                pass
        width = width or 80
```        