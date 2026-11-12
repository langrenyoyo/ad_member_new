package com.example.idiomquiz.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [IdiomEntity::class, AnswerRecordEntity::class, UserStatsEntity::class],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun idiomDao(): IdiomDao
    abstract fun answerRecordDao(): AnswerRecordDao
    abstract fun statsDao(): StatsDao

    companion object {
        @Volatile
        private var instance: AppDatabase? = null

        fun get(context: Context): AppDatabase = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(
                context.applicationContext,
                AppDatabase::class.java,
                "idiom_quiz.db"
            ).build().also { instance = it }
        }
    }
}
