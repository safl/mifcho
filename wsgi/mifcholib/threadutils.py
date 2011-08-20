#!/usr/bin/env python
"""ThreadUtils."""
import threading
import logging
import Queue
from Queue import Empty

class Worker(threading.Thread):
    """A common interface for non-WorkerPool threads."""

    wrk_count = 0

    def __init__(self, name):

        self.running      = False
        thread_name       = "Worker-%d-%s" % (Worker.wrk_count, name)
        Worker.wrk_count  += 1
        
        threading.Thread.__init__(self, name=thread_name)
        self.daemon = True

    def run(self):
        
        self.running = True
        while self.running:
            self.work()

    def work(self):
        """Must be overridden."""
        logging.error('Nothing implemented...')

    def stop(self):
        """Stop the worker."""
        self.running = False
        self.deallocate()
        
    def deallocate(self):
        pass

class WorkerPool(threading.Thread):
    """
    Basic WorkerPool implementation, each thread polls a queue for jobs.
    Executing the work() method when retrieving a job from the queue.

    WorkerPool interface: start/stop/order
    Override the work() method
    Optionally override the deallocate() method
    """

    w_count = 0

    def __init__(self, name, max_instances=4):

        thread_name = 'WorkerPool-%d-%s' % (WorkerPool.w_count, name)
        WorkerPool.w_count += 1
        
        self.running = True

        self.max_instances  = int(max_instances)
        self.instances      = []
        self.work_queue     = Queue.Queue()

        for i in xrange(self.max_instances):
            w_name = "%s-%d" % (thread_name, i)
            w = threading.Thread(name=w_name, target=self._work_loop)
            self.instances.append(w)

        threading.Thread.__init__(self, name=thread_name+'-main')
        self.daemon = True

    def _work_loop(self):
        
        while self.running:
            try:

                work = self.work_queue.get(True, 0.5)
                if work:
                    self.work(work)
                self.work_queue.task_done()
            
            except Empty: # we dont care that the queue is empty
                                # We just want to re-evaluate self.running
                pass    
            except Queue.Empty: # we dont care that the queue is empty
                                # We just want to re-evaluate self.running
                pass
            except:             # Something much worse happened
                logging.error("Bad mojo when working...", exc_info=3)

    def run(self):
        
        for w in self.instances: # Start worker-threads
            w.start()

        for w in self.instances: # Wait for them to exit
            w.join()

    def stop(self):
        """Stop the WorkerPool."""

        self.running = False
        self.deallocate()

    def order(self, work):
        """Place a job on the queue."""
        self.work_queue.put_nowait(work)

    def work(self, work):
        """Execute the actual work, override this method."""
        logging.error('Executed work method of the base WorkerPool, nothing done.')

    def deallocate(self):
        """Override this function to abort any blocking calls in the Handler."""
        pass
