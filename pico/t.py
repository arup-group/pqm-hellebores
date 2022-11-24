def value_gauge(v, low, high):
    # scale readings over 50 characters
    v_pos = round((v - low)/(high - low) * 50)
    out = ''
    for i in range(0, v_pos):
        out = out + '-'
    out = out + '>'
    for i in range(v_pos+1, high+1):
        out = out + ' '
    print(out, end='\r')



