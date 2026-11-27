console.log('MINWORKER_OK'); console.log('self?', typeof self, 'postMessage?', typeof postMessage); parentPort && parentPort.postMessage('hello');
