class TaskQueue {
  constructor({ concurrency = 1 }) {
    this.concurrency = concurrency;
    this.running = 0;
    this.pending = [];
  }

  enqueue(task) {
    return new Promise((resolve, reject) => {
      this.pending.push({ task, resolve, reject });
      this.pump();
    });
  }

  pump() {
    while (this.running < this.concurrency && this.pending.length > 0) {
      const item = this.pending.shift();
      this.running += 1;

      Promise.resolve()
        .then(() => item.task())
        .then((result) => item.resolve(result))
        .catch((error) => item.reject(error))
        .finally(() => {
          this.running -= 1;
          this.pump();
        });
    }
  }
}

module.exports = {
  TaskQueue,
};
