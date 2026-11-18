from datetime import datetime
now=datetime.now()
print(now)
a='dd'
print(a+str(now).replace(' ','_').replace(':','-'))