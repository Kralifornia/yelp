import operator
from scipy import spatial
from tripadvisor.fourcity import extractor
from tripadvisor.fourcity import fourcity_clusterer

__author__ = 'fpena'


class CluCFEuc:

    def __init__(self, reviews):
        self.reviews = reviews
        self.user_dictionary = extractor.initialize_users(self.reviews)
        print('Users Initialized')
        self.user_cluster_dictionary = fourcity_clusterer.build_user_clusters(self.reviews)
        print('User cluster built')
        self.user_ids = extractor.get_groupby_list(self.reviews, 'user_id')
        self.item_ids = extractor.get_groupby_list(self.reviews, 'offering_id')
        self.user_reviews_dictionary = fourcity_clusterer.build_user_reviews_dictionary(self.reviews, self.user_ids)
        print('User reviews dictionary built')
        self.user_similarity_matrix = {}
        self.build_user_similarities_matrix()
        print('Users similarities matrix built')

    def predict_rating(self, user_id, item_id):
        """
        Predicts the rating the user will give to the hotel

        :param user_id: the ID of the user
        :param item_id: the ID of the hotel
        :return: a float between 1 and 5 with the predicted rating
        """
        if user_id not in self.user_reviews_dictionary:
            return None

        # if True:
        #     return 3.9

        cluster_name = self.user_dictionary[user_id].cluster

        # We remove the given user from the cluster in order to avoid bias
        cluster_users = list(self.user_cluster_dictionary[cluster_name])
        cluster_users.remove(user_id)

        similarities_sum = 0.
        similarities_ratings_sum = 0.
        num_users = 0
        for cluster_user in cluster_users:
            cluster_user_overall_rating = self.user_dictionary[cluster_user].average_overall_rating
            users_similarity = self.user_similarity_matrix[cluster_user][user_id]

            if item_id in self.user_dictionary[cluster_user].item_ratings:
                cluster_user_item_rating = self.user_dictionary[cluster_user].item_ratings[item_id]
                similarities_sum += users_similarity
                similarities_ratings_sum += users_similarity * (cluster_user_item_rating - cluster_user_overall_rating)
                # similarities_ratings_sum += (cluster_user_item_rating - cluster_user_overall_rating)
                num_users += 1
        predicted_rating = None

        if similarities_sum > 0:
            user_average_rating = self.user_dictionary[user_id].average_overall_rating
            predicted_rating = \
                user_average_rating + similarities_ratings_sum / similarities_sum
            # predicted_rating = \
            #     user_average_rating + similarities_ratings_sum / num_users #/ similarities_sum

            if predicted_rating > 5:
                predicted_rating = 5
            elif predicted_rating < 1:
                predicted_rating = 1

        return predicted_rating

    def predict_ratings_list(self, reviews):
        """
        For each one of the reviews this method predicts the rating for the
        user and item contained in the review and also returns the error
        between the predicted rating and the actual rating the user gave to the
        item

        :param reviews: a list of reviews (the test data)
        :return: a tuple with a list of the predicted ratings and the list of
        errors for those predictions
        """
        predicted_ratings = []
        errors = []

        index = 0
        print('CluCFEuc')
        print('Total reviews: %i' % len(self.reviews))

        for review in reviews:
            # print('Index: %i' % index)
            index += 1

            user_id = review['user_id']
            hotel_id = review['offering_id']
            predicted_rating = self.predict_rating(user_id, hotel_id)
            actual_rating = None
            if user_id in self.user_dictionary and hotel_id in self.user_dictionary[user_id].item_ratings:
                actual_rating = self.user_dictionary[user_id].item_ratings[hotel_id]

            error = None

            if predicted_rating is not None and actual_rating is not None:
                error = abs(predicted_rating - actual_rating)

            predicted_ratings.append(predicted_rating)
            errors.append(error)

        return predicted_ratings, errors

    def predict_user_ratings(self, user, items):
        """
        Predicts the ratings that this user will give to each of the items
        contained in this object's reviews

        :param user: the ID of the user
        :return: a dictionary where each item ID is the key and the value is the
         predicted rating for that item
        """
        predicted_ratings = {}

        for item in items:
            predicted_rating = self.predict_rating(user, item)
            if predicted_rating is not None:
                predicted_ratings[item] = predicted_rating

        return predicted_ratings

    def calculate_user_recall(self, user, n):
        """
        Calculates the recall of this recommender system for a given user.
        The recall is defined as the number of correct hits divided by the
        total number of items that this user likes

        :param user: the user ID
        :param n: the number of items to be displayed to the user
        :return: the recall of this recommender system
        """
        num_hits = 0
        favorite_items = extractor.get_five_star_hotels_from_user(self.user_reviews_dictionary[user], 4.5)

        if not favorite_items:
            return None

        items = self.item_ids + favorite_items
        length = n + len(favorite_items)
        predicted_ratings = self.predict_user_ratings(user, items)
        sorted_ratings = sorted(predicted_ratings.iteritems(), key=operator.itemgetter(1))
        sorted_ratings.reverse()
        sorted_ratings = sorted_ratings[:length]

        for item, rating in sorted_ratings:
            if item in favorite_items:
                print('Item: %s\t Rating: %f' % (item, rating))
                num_hits += 1

        recall = float(num_hits) / float(len(favorite_items))
        return recall

    def calculate_recall(self, users, n):
        """
        Calculates the recall of this recommender system for a list of users.
        The recall is defined as the number of correct hits divided by the
        total number of items that this user likes. This method returns the
        average of the recalls for each user

        :param users: a list with the IDs of the users
        :param n: the number of items to be displayed to the user
        :return: the recall of this recommender system
        """

        total_recall = 0
        num_cycles = 0
        index = 0

        for user in users:
            print('Index %i' % index)
            index += 1
            recall = self.calculate_user_recall(user, n)
            if recall is not None:
                total_recall += recall
                num_cycles += 1
                print('Recall: %f' % recall)

        average_recall = total_recall / float(num_cycles)
        print('Average recall: %f' % average_recall)

        return average_recall

    def calculate_users_similarity(self, user_id1, user_id2):
        """
        Calculates the similarity between two users based on how similar are their
        ratings in the reviews

        :param user_id1: the ID of user 1
        :param user_id2: the ID of user 2
        :return: a float with the similarity between the two users. Since this
        function is based on euclidean distance to calculate the similarity, a
        similarity of 0 indicates that the users share exactly the same tastes
        """
        user_weights1 = self.user_dictionary[user_id1].criteria_weights
        user_weights2 = self.user_dictionary[user_id2].criteria_weights

        return fourcity_clusterer.calculate_euclidean_distance(user_weights1, user_weights2)
        # return spatial.distance.cosine(user_weights1, user_weights2)
        # return 0

    def build_user_similarities_matrix(self):
        """
        Builds a matrix that contains the similarity between every pair of users
        in the dataset of this recommender system. This is particularly useful
        to prevent repeating the same calculations in each cycle

        """
        for user1 in self.user_ids:
            self.user_similarity_matrix[user1] = {}
            for user2 in self.user_ids:
                self.user_similarity_matrix[user1][user2] = self.calculate_users_similarity(user1, user2)