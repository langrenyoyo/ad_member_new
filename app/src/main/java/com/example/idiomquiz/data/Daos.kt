package com.example.idiomquiz.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface IdiomDao {
    @Query("SELECT COUNT(*) FROM idioms")
    suspend fun count(): Int

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(items: List<IdiomEntity>)

    @Query("SELECT * FROM idioms ORDER BY word")
    suspend fun getAll(): List<IdiomEntity>

    @Query("SELECT * FROM idioms WHERE id = :id LIMIT 1")
    suspend fun getById(id: Long): IdiomEntity?

    @Query("UPDATE idioms SET isFavorite = :isFavorite WHERE id = :id")
    suspend fun setFavorite(id: Long, isFavorite: Boolean)
}

@Dao
interface AnswerRecordDao {
    @Insert
    suspend fun insert(record: AnswerRecordEntity)

    @Query(
        "SELECT idiomId FROM answer_records " +
            "WHERE isCorrect = 0 GROUP BY idiomId ORDER BY MAX(answeredAt) DESC"
    )
    suspend fun getMistakeIds(): List<Long>

    @Query("SELECT COUNT(DISTINCT idiomId) FROM answer_records WHERE isCorrect = 0")
    suspend fun countMistakes(): Int

    @Query("DELETE FROM answer_records WHERE idiomId = :idiomId")
    suspend fun deleteForIdiom(idiomId: Long)

    @Query("DELETE FROM answer_records")
    suspend fun clear()
}

@Dao
interface StatsDao {
    @Query("SELECT * FROM user_stats WHERE id = 1 LIMIT 1")
    suspend fun get(): UserStatsEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(stats: UserStatsEntity)
}
