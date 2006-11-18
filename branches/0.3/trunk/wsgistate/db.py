# Copyright (c) 2005, the Lawrence Journal-World
# Copyright (c) 2006 L. C. Rees
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    1. Redistributions of source code must retain the above copyright notice, 
#       this list of conditions and the following disclaimer.
#    
#    2. Redistributions in binary form must reproduce the above copyright 
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
#    3. Neither the name of Django nor the names of its contributors may be used
#       to endorse or promote products derived from this software without
#       specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

'''Database cache backend.'''

import time
from datetime import datetime
try:
    from sqlalchemy import *
except ImportError:
    raise ImportError('DbCache module requires the SQLAlchemy package ' \
        'from http://www.sqlalchemy.org/')
from wsgistate.base import BaseCache

__all__ = ['DbCache']


class DbCache(BaseCache):     

    '''Database cache backend.'''

    def __init__(self, *a, **kw):
        super(DbCache, self).__init__(self, *a, **kw)
        # Bind metadata
        self._metadata = BoundMetaData(a[0])
        # Make cache
        self._cache = Table('cache', self._metadata,
            Column('id', Integer, primary_key=True, nullable=False, unique=True),
            Column('cache_key', String(60), nullable=False),
            Column('value', PickleType, nullable=False),
            Column('expires', DateTime, nullable=False))
        # Create cache if it does not exist
        if not self._cache.exists(): self._cache.create()
        max_entries = kw.get('max_entries', 300)
        try:
            self._max_entries = int(max_entries)
        except (ValueError, TypeError):
            self._max_entries = 300

    def get(self, key, default=None):
        '''Fetch a given key from the cache.  If the key does not exist, return
        default, which itself defaults to None.

        @param key Keyword of item in cache.
        @param default Default value (default: None)
        '''
        row = self._cache.select().execute(cache_key=key).fetchone()
        if row is None: return default
        if row.expires < datetime.now().replace(microsecond=0):
            self.delete(key)
            return default
        return row.value

    def set(self, key, val):
        '''Set a value in the cache.

        @param key Keyword of item in cache.
        @param value Value to be inserted in cache.        
        '''
        
        timeout = self.timeout
        # Get count
        num = self._cache.count().execute().fetchone()[0]
        if num > self._max_entries: self._cull()
        # Get expiration time
        exp = datetime.fromtimestamp(time.time() + timeout).replace(microsecond=0)        
        try:
            # Update database if key already present
            if key in self:
                self._cache.update(self._cache.c.cache_key==key).execute(value=val, expires=exp)
            # Insert new key if key not present
            else:            
                self._cache.insert().execute(cache_key=key, value=val, expires=exp)
        # To be threadsafe, updates/inserts are allowed to fail silently
        except: pass
       
    def delete(self, key):
        '''Delete a key from the cache, failing silently.

        @param key Keyword of item in cache.
        '''
        self._cache.delete().execute(cache_key=key) 

    def _cull(self):
        '''Remove items in cache that have timed out.'''
        now = datetime.now().replace(microsecond=0)
        self._cache.delete(self._cache.c.expires < now).execute()