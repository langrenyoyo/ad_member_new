package com.example.idiomquiz

import com.example.idiomquiz.data.BackgroundRetry
import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.atomic.AtomicInteger

class BackgroundRetryTest {
    @Test fun cancelledTaskCannotRestoreCooldownAfterCancel() = runBlocking {
        val scope = CoroutineScope(SupervisorJob() + coroutineContext.minusKey(Job))
        val worker = BackgroundRetry(scope, 60_000)
        val started = CompletableDeferred<Unit>()
        val cleanup = CompletableDeferred<Unit>()
        val cleaned = CompletableDeferred<Unit>()
        try {
            worker.schedule {
                try { started.complete(Unit); awaitCancellation() }
                finally { withContext(NonCancellable) { cleanup.await() }; cleaned.complete(Unit) }
            }
            started.await()
            worker.cancel()
            cleanup.complete(Unit)
            cleaned.await(); yield()
            val replacement = CompletableDeferred<Unit>()
            worker.schedule { replacement.complete(Unit) }
            withTimeout(2000) { replacement.await() }
        } finally { cleanup.complete(Unit); scope.cancel() }
    }
    @Test fun workerDoesNotBlockCallerAndCoalescesConcurrentTriggers() = runBlocking {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        val worker = BackgroundRetry(scope, 0)
        val started = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val calls = AtomicInteger()
        try {
            worker.schedule { calls.incrementAndGet(); started.complete(Unit); release.await() }
            withTimeout(2000) { started.await() }
            repeat(20) { worker.schedule { calls.incrementAndGet() } }
            assertEquals(1, calls.get())
            assertFalse(release.isCompleted)
            // A foreground action completes while recovery is still suspended.
            assertEquals("wallet", withTimeout(1000) { async { "wallet" }.await() })
        } finally { release.complete(Unit); scope.cancel() }
    }

    @Test fun failedWorkerKeepsCooldownAndCancellationReleasesIt() = runBlocking {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        val worker = BackgroundRetry(scope, 60_000)
        val started = CompletableDeferred<Unit>()
        val calls = AtomicInteger()
        try {
            worker.schedule { calls.incrementAndGet(); started.complete(Unit); throw java.io.IOException() }
            withTimeout(2000) { started.await() }
            worker.schedule { calls.incrementAndGet() }
            assertEquals(1, calls.get())
            worker.cancel()
        } finally { scope.cancel() }
    }
}
