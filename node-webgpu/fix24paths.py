for p in [r'E:\gta\playgta5\node-webgpu\harness.js', r'E:\gta\playgta5\node-webgpu\worker-boot.js']:
    s = open(p, encoding='utf-8').read()
    s = s.replace("path.join(__dirname, 'node_modules', 'webgpu')", "'E:/gta/playgta5/node24/wgpu/node_modules/webgpu'")
    open(p, 'w', encoding='utf-8', newline='').write(s)
    print('UPDATED', p)
